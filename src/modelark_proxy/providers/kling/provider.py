"""Kling video generation behind the provider contract.

Kling 3.0, 2.6 and 2.5 Turbo use the legacy `/v1/videos/...` endpoints, which
alone offer negative prompts, per-shot control, elements and voices; Kling 3.0
Turbo only exists in the new API (model in the path, `/tasks` for status).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ...config import Settings
from ...downloads import host_allowed, stream_remote
from ...errors import ApiError, openai_error
from ...ids import decode_video_id
from ...outputs import OutputStore
from ...provider_jobs import TERMINAL_STATUSES, ProviderJobStore
from ...references import ReferenceResolver
from ...schemas import VideoObject
from ...unified import UnifiedRequest, normalize_request
from ...validation import ContractError, validate
from ..base import ProviderUnavailable, strip_model_namespace
from .assets import KlingAssets, native_id, parse_asset_id
from .client import KlingClient
from .models import (
    EFFECT_IMAGES,
    MODELS,
    VIRTUAL_MODELS,
    KlingModel,
    QUALITY_RESOLUTIONS,
    RESOLUTION_MODES,
    canonical_model,
    kling_capabilities,
)

logger = logging.getLogger(__name__)
RUNNING = {"submitted", "processing"}
# Documented Kling routes the native passthrough forwards (image APIs and
# virtual try-on are out of scope by decision).
NATIVE_PREFIXES = (
    "/v1/videos/",
    "/v1/audio/",
    "/v1/general/",
    "/text-to-video/",
    "/image-to-video/",
    "/omni-video/",
    "/motion-control/",
    "/tasks",
    "/solutions",
    "/account/costs",
)
NATIVE_EXCLUDED = ("/solutions/virtual_try_on",)
NEW_API_KINDS = (
    "/text-to-video/",
    "/image-to-video/",
    "/omni-video/",
    "/motion-control/",
)
# Synchronous helpers that create no video task.
SYNC_VIDEO_PATHS = (
    "/v1/videos/identify-face",
    "/v1/videos/image-recognize",
    "/v1/videos/multi-elements/",
)
SUCCEEDED = {"succeed", "succeeded"}


class KlingProvider:
    name = "kling"

    def __init__(
        self,
        settings: Settings,
        client: KlingClient,
        jobs: ProviderJobStore,
        outputs: OutputStore,
        references: ReferenceResolver,
        download_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.jobs = jobs
        self.outputs = outputs
        self.references = references
        self.download_transport = download_transport
        self.last_polled: dict[str, float] = {}
        self.assets = KlingAssets(client, references)
        # Set by the app; drives multi-step jobs such as lip sync.
        self.runner: Any = None

    def owns_video(self, video_id: str) -> bool:
        return video_id.startswith("vid-kling-")

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": model.id,
                "object": "model",
                "owned_by": "kling",
                "name": model.label,
                "capabilities": kling_capabilities(model.id).to_dict(),
            }
            for model in MODELS.values()
        ] + [
            {
                "id": model_id,
                "object": "model",
                "owned_by": "kling",
                "name": label,
                "virtual": True,
                "capabilities": kling_capabilities(model_id).to_dict(),
            }
            for model_id, label in VIRTUAL_MODELS.items()
        ]

    # --- create -------------------------------------------------------------

    async def create_video(
        self, data: dict[str, Any], upload: UploadFile | None
    ) -> VideoObject:
        if upload is not None:
            raise ContractError(
                "Kling models do not accept input_reference uploads; use references",
                code="unsupported_parameter",
                param="input_reference",
            )
        model_id = canonical_model(strip_model_namespace(str(data.get("model", ""))))
        if model_id in VIRTUAL_MODELS:
            # A virtual model does exactly one task.
            data = {
                **data,
                "task": data.get("task")
                or next(iter(kling_capabilities(model_id).tasks)),
            }
        request = normalize_request(data)
        if model_id is None:
            raise ProviderUnavailable(
                f"Model '{request.model}' is not available on this proxy"
            )
        request.model = model_id
        if model_id in VIRTUAL_MODELS:
            return await self._create_virtual(request)
        quality = request.params.get("quality")
        if quality in QUALITY_RESOLUTIONS:
            request.params.pop("quality")
            request.params.setdefault("resolution", QUALITY_RESOLUTIONS[quality])
        caps = kling_capabilities(model_id)
        if request.task == "multi_shot":
            self._check_shots(request)
        if any(r["type"] == "voice" for r in request.references):
            # Kling only speaks with a voice when sound is on.
            request.params.setdefault("generate_audio", True)
        options = request.provider_options.get("kling") or {}
        unknown = sorted(set(options) - set(caps.provider_options))
        if unknown:
            raise ContractError(
                f"Unsupported provider_options.kling fields: {', '.join(unknown)}",
                code="unsupported_parameter",
                param="provider_options",
            )
        request, adjustments = validate(caps, request)
        model = MODELS[model_id]
        if model.omni:
            path = "/v1/videos/omni-video"
            body = await self._omni_body(request, model, options)
            created = await self.client.call("POST", path, json=body)
            upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
            return self._register(model_id, request, upstream, adjustments)
        if request.task == "motion_control":
            assert model.legacy_name is not None
            path = "/v1/videos/motion-control"
            body = await self._motion_body(request, model.legacy_name, options)
            created = await self.client.call("POST", path, json=body)
            upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
            return self._register(model_id, request, upstream, adjustments)
        images = {
            reference["role"]: await self._image(reference)
            for reference in request.references
            if reference["type"] == "image"
        }
        steering = self._steering(request, images)
        if model.legacy_name:
            path = "/v1/videos/image2video" if images else "/v1/videos/text2video"
            created = await self.client.call(
                "POST",
                path,
                json={
                    **self._legacy_body(request, model.legacy_name, images),
                    **steering,
                },
            )
            upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
        else:
            path = "image-to-video" if images else "text-to-video"
            created = await self.client.call(
                "POST", f"/{path}/{model_id}", json=self._new_body(request, images)
            )
            upstream = {"api": "new", "task_id": created["id"]}
        return self._register(model_id, request, upstream, adjustments)

    def _register(
        self,
        model_id: str,
        request: UnifiedRequest,
        upstream: dict[str, Any],
        adjustments: list[dict[str, Any]],
    ) -> VideoObject:
        job = self.jobs.create(
            "kling",
            model_id,
            request.task,
            {
                "prompt": request.prompt,
                "seconds": request.params.get("seconds"),
                "params": request.params,
            },
            upstream=upstream,
        )
        if adjustments:
            self.jobs.update(job["id"], adjustments=adjustments)
        return self.jobs.to_video(self.jobs.get(job["id"]) or job)

    # --- lip sync and avatar ----------------------------------------------------

    async def _create_virtual(self, request: UnifiedRequest) -> VideoObject:
        caps = kling_capabilities(request.model)
        quality = request.params.pop("quality", None)
        if quality in QUALITY_RESOLUTIONS:
            request.params.setdefault("resolution", QUALITY_RESOLUTIONS[quality])
        request, adjustments = validate(caps, request)
        if request.task in {"text_to_audio", "video_to_audio"}:
            return await self._create_audio(request, adjustments)
        if request.task == "effect":
            return await self._create_effect(request, adjustments)
        if request.task == "multi_element_edit":
            return self._create_multi_element(request, adjustments)
        speech = request.params.get("speech") or {}
        audio = next((r for r in request.references if r["role"] == "speech"), None)
        if audio is None and not speech.get("text"):
            raise ContractError(
                f"{request.task} needs an audio reference with role speech or speech.text",
                code="reference_limit",
                param="references",
            )
        if audio is None and not speech.get("voice"):
            raise ContractError(
                "speech.voice is required for speech.text", param="speech"
            )
        if request.task == "lip_sync":
            # Face detection, text-to-speech and rendering run in the worker.
            job = self.jobs.create(
                "kling",
                request.model,
                request.task,
                {
                    "prompt": request.prompt,
                    "params": request.params,
                    "references": request.references,
                },
                worker=True,
            )
            self.jobs.update(
                job["id"], state={"step": "identify"}, adjustments=adjustments or None
            )
            if self.runner is not None:
                self.runner.schedule(job["id"])
            return self.jobs.to_video(self.jobs.get(job["id"]) or job)
        subject = next(r for r in request.references if r["role"] == "subject")
        body: dict[str, Any] = {"image": await self._image(subject)}
        body.update(await self._speech(audio, speech, max_seconds=300))
        if request.prompt:
            body["prompt"] = request.prompt
        body["mode"] = RESOLUTION_MODES[request.params.get("resolution", "720p")]
        if request.params.get("watermark"):
            body["watermark_info"] = {"enabled": True}
        path = "/v1/videos/avatar/image2video"
        created = await self.client.call("POST", path, json=body)
        upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
        return self._register(request.model, request, upstream, adjustments)

    async def _create_audio(
        self, request: UnifiedRequest, adjustments: list[dict[str, Any]]
    ) -> VideoObject:
        """Text-to-audio (sound effects, music) and video-to-audio (a soundtrack)."""
        if request.task == "text_to_audio":
            path = "/v1/audio/text-to-audio"
            body: dict[str, Any] = {
                "prompt": request.prompt,
                "duration": float(request.params.get("seconds", 5)),
            }
        else:
            path = "/v1/audio/video-to-audio"
            options = request.params.get("audio") or {}
            video = next(r for r in request.references if r["role"] == "base_video")
            body = await self._video_source(video)
            if request.prompt:
                body["sound_effect_prompt"] = request.prompt
            if options.get("bgm_prompt"):
                body["bgm_prompt"] = options["bgm_prompt"]
            if "asmr" in options:
                body["asmr_mode"] = bool(options["asmr"])
        created = await self.client.call("POST", path, json=body)
        upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
        return self._register(request.model, request, upstream, adjustments)

    async def _speech(
        self,
        audio: dict[str, Any] | None,
        speech: dict[str, Any],
        *,
        max_seconds: int,
    ) -> dict[str, Any]:
        """`audio_id` from text-to-speech or a `sound_file` (URL or base64)."""
        if audio is None:
            audio_id, _ = await self._tts(speech)
            return {"audio_id": audio_id}
        url = audio.get("url")
        if (
            isinstance(url, str)
            and url.startswith("https://")
            and not self.references.is_own_media(url)
        ):
            return {"sound_file": url}
        media = await self.references.fetch(audio)
        if len(media.data) > 5 * 1024 * 1024:
            raise ContractError(
                "Kling accepts audio files up to 5 MB",
                code="reference_limit",
                param="references",
            )
        return {"sound_file": media.base64}

    async def _tts(self, speech: dict[str, Any]) -> tuple[str, int]:
        """Kling text-to-speech; returns the audio ID and its length in ms."""
        data = await self.client.call(
            "POST",
            "/v1/audio/tts",
            json={
                "text": speech["text"],
                "voice_id": speech["voice"],
                "voice_language": speech.get("language", "en"),
                "voice_speed": float(speech.get("speed", 1.0)),
            },
        )
        clip = ((data.get("task_result") or {}).get("audios") or [{}])[0]
        if not clip.get("id"):
            raise ApiError(
                "Kling text-to-speech returned no audio", 502, "upstream_error"
            )
        return str(clip["id"]), int(float(clip.get("duration") or 0) * 1000)

    async def _create_effect(
        self, request: UnifiedRequest, adjustments: list[dict[str, Any]]
    ) -> VideoObject:
        effect = str(request.params["effect"])
        images = [r for r in request.references if r["type"] == "image"]
        expected = EFFECT_IMAGES[effect]
        if len(images) != expected:
            raise ContractError(
                f"Effect {effect} takes exactly {expected} image(s)",
                code="reference_limit",
                param="references",
            )
        encoded = [await self._image(image) for image in images]
        body = {
            "effect_scene": effect,
            "input": {"image": encoded[0]} if expected == 1 else {"images": encoded},
        }
        path = "/v1/videos/effects"
        created = await self.client.call("POST", path, json=body)
        upstream = {"api": "legacy", "path": path, "task_id": created["task_id"]}
        return self._register(request.model, request, upstream, adjustments)

    def _create_multi_element(
        self, request: UnifiedRequest, adjustments: list[dict[str, Any]]
    ) -> VideoObject:
        """Validate the selection up front; the session itself runs in the worker."""
        mode = request.params.get("edit_mode")
        images = [r for r in request.references if r["type"] == "image"]
        allowed = {"addition": (1, 2), "swap": (1, 1), "removal": (0, 0)}
        if mode not in allowed:
            raise ContractError(
                "edit_mode must be addition, swap or removal", param="edit_mode"
            )
        low, high = allowed[mode]
        if not low <= len(images) <= high:
            raise ContractError(
                f"edit_mode={mode} takes {low} to {high} image(s)",
                code="reference_limit",
                param="references",
            )
        selections = request.params.get("selections")
        if not isinstance(selections, list) or not 1 <= len(selections) <= 10:
            raise ContractError("selections needs 1 to 10 frames", param="selections")
        for selection in selections:
            points = selection.get("points") if isinstance(selection, dict) else None
            if (
                not isinstance(selection.get("frame_index"), int)
                or selection["frame_index"] < 0
                or not isinstance(points, list)
                or not 1 <= len(points) <= 10
                or not all(
                    isinstance(point, dict)
                    and all(
                        isinstance(point.get(axis), int | float)
                        and 0 <= point[axis] <= 1
                        for axis in ("x", "y")
                    )
                    for point in points
                )
            ):
                raise ContractError(
                    "Each selection needs a frame_index and 1 to 10 points with x, y in [0, 1]",
                    param="selections",
                )
        job = self.jobs.create(
            "kling",
            request.model,
            request.task,
            {
                "prompt": request.prompt,
                "params": request.params,
                "references": request.references,
            },
            worker=True,
        )
        self.jobs.update(
            job["id"], state={"step": "init"}, adjustments=adjustments or None
        )
        if self.runner is not None:
            self.runner.schedule(job["id"])
        return self.jobs.to_video(self.jobs.get(job["id"]) or job)

    async def _run_multi_element(self, job: dict[str, Any]) -> None:
        """Init the selection session, mark the objects, then submit the edit.

        Progress is stored after every call, so a restart resumes the session.
        """
        state = dict(job["state"] or {})
        request = job["request"]
        params = request["params"]
        references = request["references"]
        if state.get("step") == "init":
            video = next(r for r in references if r["role"] == "base_video")
            self.jobs.update(
                job["id"], status="in_progress", provider_status="selection"
            )
            session = await self.client.call(
                "POST",
                "/v1/videos/multi-elements/init-selection",
                json=await self._video_source(video),
            )
            state = {
                "step": "select",
                "session_id": session["session_id"],
                "seconds": float(session.get("original_duration") or 0),
                "selected": 0,
            }
            self.jobs.update(job["id"], state=state)
        selections = params["selections"]
        while state["selected"] < len(selections):
            selection = selections[state["selected"]]
            await self.client.call(
                "POST",
                "/v1/videos/multi-elements/add-selection",
                json={
                    "session_id": state["session_id"],
                    "frame_index": selection["frame_index"],
                    "points": selection["points"],
                },
            )
            state["selected"] += 1
            self.jobs.update(job["id"], state=state)
        seconds = state["seconds"]
        # Kling renders 5 s for 2-5 s inputs and 10 s for 7-10 s inputs.
        if seconds <= 5.5:
            duration = "5"
        elif seconds >= 6.5:
            duration = "10"
        else:
            raise ApiError(
                "Multi-element editing needs a 2-5 s or 7-10 s video",
                400,
                "reference_limit",
            )
        body: dict[str, Any] = {
            "session_id": state["session_id"],
            "edit_mode": params["edit_mode"],
        }
        images = [r for r in references if r["type"] == "image"]
        if images:
            body["image_list"] = [
                {"image": await self._image(image)} for image in images
            ]
        if request["prompt"]:
            body["prompt"] = request["prompt"]
        if params.get("negative_prompt"):
            body["negative_prompt"] = params["negative_prompt"]
        body["mode"] = RESOLUTION_MODES[params.get("resolution", "720p")]
        body["duration"] = duration
        if params.get("watermark"):
            body["watermark_info"] = {"enabled": True}
        path = "/v1/videos/multi-elements"
        created = await self.client.call("POST", path, json=body)
        self.jobs.update(
            job["id"],
            upstream={"api": "legacy", "path": path, "task_id": created["task_id"]},
            state={**state, "step": "rendering"},
            provider_status="submitted",
        )

    async def run_job(self, job: dict[str, Any]) -> None:
        """Worker step for multi-step jobs (lip sync, multi-element editing)."""
        state = job["state"] or {}
        if state.get("step") == "rendering":
            await self._poll(job)
            return
        if job["task"] == "multi_element_edit":
            await self._run_multi_element(job)
            return
        request = job["request"]
        params = request["params"]
        speech = params.get("speech") or {}
        options = params.get("audio") or {}
        references = request["references"]
        video = next(r for r in references if r["role"] == "base_video")
        audio = next((r for r in references if r["role"] == "speech"), None)
        self.jobs.update(
            job["id"], status="in_progress", provider_status="face_identification"
        )
        faces = await self.client.call(
            "POST", "/v1/videos/identify-face", json=await self._video_source(video)
        )
        candidates = faces.get("face_data") or []
        if not candidates:
            raise ApiError("Kling found no face in the video", 400, "invalid_request")
        face = next(
            (f for f in candidates if f.get("face_id") == options.get("face_id")), None
        )
        if face is None:
            face = max(
                candidates, key=lambda f: int(f["end_time"]) - int(f["start_time"])
            )
        face_ms = int(face["end_time"]) - int(face["start_time"])
        if audio is None:
            audio_id, length_ms = await self._tts(speech)
            sound: dict[str, Any] = {"audio_id": audio_id}
        else:
            sound = await self._speech(audio, speech, max_seconds=60)
            length_ms = min(face_ms, 60_000)
        choice: dict[str, Any] = {
            "face_id": face["face_id"],
            **sound,
            "sound_start_time": int(options.get("start_ms", 0)),
            "sound_end_time": int(options.get("end_ms", length_ms)),
            "sound_insert_time": int(options.get("insert_at_ms", face["start_time"])),
        }
        if "volume" in options:
            choice["sound_volume"] = options["volume"]
        if "original_volume" in options:
            choice["original_audio_volume"] = options["original_volume"]
        body: dict[str, Any] = {
            "session_id": faces["session_id"],
            "face_choose": [choice],
        }
        if params.get("watermark"):
            body["watermark_info"] = {"enabled": True}
        path = "/v1/videos/advanced-lip-sync"
        created = await self.client.call("POST", path, json=body)
        self.jobs.update(
            job["id"],
            upstream={"api": "legacy", "path": path, "task_id": created["task_id"]},
            state={"step": "rendering", "face_id": face["face_id"]},
            provider_status="submitted",
        )

    async def _video_source(self, reference: dict[str, Any]) -> dict[str, Any]:
        """Kling's own video ID for earlier Kling jobs, otherwise a fetchable URL."""
        if reference.get("task_id"):
            source = self.jobs.get(decode_video_id(str(reference["task_id"])))
            outputs = (source or {}).get("outputs") or []
            index = int(reference.get("output") or 0)
            if source and source["provider"] == "kling" and index < len(outputs):
                kling_id = outputs[index].get("kling_video_id")
                if kling_id:
                    return {"video_id": kling_id}
        return {"video_url": await self.references.public_url(reference)}

    async def _motion_body(
        self, request: UnifiedRequest, model_name: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        """`/v1/videos/motion-control`: a character moves like the motion video."""
        subject = next((r for r in request.references if r["role"] == "subject"), None)
        motion = next(r for r in request.references if r["role"] == "motion")
        steering = self._steering(request, {}, require_frame=False)
        if subject is None and not steering:
            raise ContractError(
                "Motion control needs a character image or element",
                code="reference_limit",
                param="references",
            )
        body: dict[str, Any] = {"model_name": model_name}
        if request.prompt:
            body["prompt"] = request.prompt
        if subject is not None:
            body["image_url"] = await self._image(subject)
        body.update(steering)
        body["video_url"] = await self.references.public_url(motion)
        # Required by Kling; "image" keeps the character's orientation.
        body["character_orientation"] = options.get("character_orientation", "image")
        if "keep_original_sound" in options:
            body["keep_original_sound"] = options["keep_original_sound"]
        body["mode"] = RESOLUTION_MODES[request.params.get("resolution", "720p")]
        if request.params.get("watermark"):
            body["watermark_info"] = {"enabled": True}
        return body

    async def _omni_body(
        self, request: UnifiedRequest, model: KlingModel, options: dict[str, Any]
    ) -> dict[str, Any]:
        """`/v1/videos/omni-video` body: typed image, element and video lists."""
        params = request.params
        videos = [r for r in request.references if r["type"] == "video"]
        if videos and params.get("generate_audio"):
            raise ContractError(
                "Kling Omni cannot generate audio together with a reference video; "
                "use provider_options.kling.keep_original_sound",
                code="unsupported_parameter",
                param="generate_audio",
            )
        assert model.legacy_name is not None
        body = self._legacy_body(request, model.legacy_name, {})
        body.pop("aspect_ratio", None)
        if request.task == "edit":
            # The edit keeps the length of the input video.
            body.pop("duration", None)
        if request.task in {"text_to_video", "multi_shot", "reference_to_video"}:
            body["aspect_ratio"] = params.get("aspect_ratio", "16:9")
        frame_types = {"first_frame": "first_frame", "last_frame": "end_frame"}
        image_list = []
        for reference in request.references:
            if reference["type"] != "image":
                continue
            item = {"image_url": await self._image(reference)}
            if reference["role"] in frame_types:
                item["type"] = frame_types[reference["role"]]
            image_list.append(item)
        if image_list:
            body["image_list"] = image_list
        body.update(self._steering(request, {}, require_frame=False))
        if videos:
            body["video_list"] = [
                {
                    "video_url": await self.references.public_url(video),
                    "refer_type": "base"
                    if video["role"] == "base_video"
                    else "feature",
                    "keep_original_sound": options.get("keep_original_sound", "no"),
                }
                for video in videos
            ]
        return body

    @staticmethod
    def _steering(
        request: UnifiedRequest, images: dict[str, str], *, require_frame: bool = True
    ) -> dict[str, Any]:
        """Legacy `element_list` / `voice_list` from element and voice assets."""
        lists: dict[str, list[dict[str, Any]]] = {}
        for reference in request.references:
            if reference["type"] not in {"element", "voice"}:
                continue
            kind, value, is_task = parse_asset_id(str(reference.get("asset_id") or ""))
            if is_task or kind != reference["type"]:
                raise ContractError(
                    f"{reference.get('asset_id')} is not a ready {reference['type']} asset",
                    code="reference_unavailable",
                    param="references",
                )
            key = "element_list" if kind == "element" else "voice_list"
            # Element IDs are numbers; voice IDs are numeric strings.
            identifier = native_id(value) if kind == "element" else value
            lists.setdefault(key, []).append({f"{kind}_id": identifier})
        if len(lists) > 1:
            raise ContractError(
                "Kling cannot combine elements and voices in one request",
                code="reference_limit",
                param="references",
            )
        if lists and require_frame and not images:
            raise ContractError(
                "Kling uses elements and voices only together with a first frame",
                code="reference_limit",
                param="references",
            )
        return lists

    @staticmethod
    def _check_shots(request: UnifiedRequest) -> None:
        mode = request.params.get("shot_mode", "customize")
        shots = request.params.get("shots") or []
        if mode == "intelligence":
            if shots or not request.prompt:
                raise ContractError(
                    "shot_mode=intelligence takes a prompt and no shots", param="shots"
                )
            return
        if not isinstance(shots, list) or not 1 <= len(shots) <= 6:
            raise ContractError("multi_shot needs 1 to 6 shots", param="shots")
        total = 0
        for shot in shots:
            prompt = shot.get("prompt") if isinstance(shot, dict) else None
            seconds = shot.get("seconds") if isinstance(shot, dict) else None
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 512:
                raise ContractError(
                    "Each shot needs a prompt of at most 512 characters", param="shots"
                )
            if not isinstance(seconds, int) or seconds < 1:
                raise ContractError(
                    "Each shot needs whole seconds of at least 1", param="shots"
                )
            total += seconds
        if request.params.setdefault("seconds", total) != total:
            raise ContractError(
                f"The shot durations add up to {total} s, not {request.params['seconds']} s",
                param="shots",
            )

    async def _image(self, reference: dict[str, Any]) -> str:
        """Kling fetches public https URLs itself; everything else goes as raw base64."""
        url = reference.get("url")
        if (
            isinstance(url, str)
            and url.startswith("https://")
            and not self.references.is_own_media(url)
        ):
            return url
        media = await self.references.fetch(reference)
        if media.mime_type not in ("image/jpeg", "image/png"):
            raise ContractError(
                f"Kling accepts JPEG or PNG images, not {media.mime_type}",
                code="reference_limit",
                param="references",
            )
        return media.base64

    @staticmethod
    def _legacy_body(
        request: UnifiedRequest, model_name: str, images: dict[str, str]
    ) -> dict[str, Any]:
        params = request.params
        body: dict[str, Any] = {"model_name": model_name}
        if request.task == "multi_shot":
            body["multi_shot"] = True
            body["shot_type"] = params.get("shot_mode", "customize")
            if body["shot_type"] == "customize":
                body["multi_prompt"] = [
                    {
                        "index": index,
                        "prompt": shot["prompt"],
                        "duration": str(shot["seconds"]),
                    }
                    for index, shot in enumerate(params["shots"], start=1)
                ]
            else:
                body["prompt"] = request.prompt
        elif request.prompt:
            body["prompt"] = request.prompt
        if params.get("negative_prompt"):
            body["negative_prompt"] = params["negative_prompt"]
        body["duration"] = str(params.get("seconds", 5))
        body["mode"] = RESOLUTION_MODES[params.get("resolution", "720p")]
        if images.get("first_frame"):
            body["image"] = images["first_frame"]
        if images.get("last_frame"):
            body["image_tail"] = images["last_frame"]
        if not images:
            body["aspect_ratio"] = params.get("aspect_ratio", "16:9")
        if "generate_audio" in params:
            body["sound"] = "on" if params["generate_audio"] else "off"
        if params.get("watermark"):
            body["watermark_info"] = {"enabled": True}
        return body

    @staticmethod
    def _new_body(request: UnifiedRequest, images: dict[str, str]) -> dict[str, Any]:
        params = request.params
        prompt = request.prompt
        if (
            request.task == "multi_shot"
            and params.get("shot_mode", "customize") == "customize"
        ):
            prompt = " ".join(
                f"shot {index}, {shot['seconds']}, {shot['prompt']};"
                for index, shot in enumerate(params["shots"], start=1)
            )
        settings: dict[str, Any] = {"resolution": params.get("resolution", "720p")}
        if not images:
            settings["aspect_ratio"] = params.get("aspect_ratio", "16:9")
        settings["duration"] = int(params.get("seconds", 5))
        body: dict[str, Any]
        if images:
            contents: list[dict[str, Any]] = []
            if prompt:
                contents.append({"type": "prompt", "text": prompt})
            contents.append({"type": "first_frame", "url": images["first_frame"]})
            body = {"contents": contents, "settings": settings}
        else:
            body = {"prompt": prompt, "settings": settings}
        if params.get("watermark"):
            body["options"] = {"watermark_info": {"enabled": True}}
        return body

    # --- native passthrough ---------------------------------------------------

    async def native(
        self,
        method: str,
        path: str,
        params: dict[str, Any],
        body: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Forward a documented Kling route; register video tasks it creates."""
        path = "/" + path.lstrip("/")
        if (
            ".." in path
            or not path.startswith(NATIVE_PREFIXES)
            or path.startswith(NATIVE_EXCLUDED)
        ):
            raise ApiError(f"{path} is not an available Kling route", 404, "not_found")
        raw = await self.client.raw(method, path, params=params or None, json=body)
        if method != "POST" or not isinstance(raw.get("data"), dict):
            return raw, None
        data = raw["data"]
        body = body or {}
        upstream: dict[str, Any] | None = None
        model = str(body.get("model_name") or "kling-native")
        if (
            path.startswith("/v1/videos/")
            and not path.startswith(SYNC_VIDEO_PATHS)
            and data.get("task_id")
        ):
            upstream = {"api": "legacy", "path": path, "task_id": data["task_id"]}
        elif path.startswith(NEW_API_KINDS) and data.get("id"):
            upstream = {"api": "new", "task_id": data["id"]}
            model = path.rsplit("/", 1)[-1]
        if upstream is None:
            return raw, None
        job = self.jobs.create(
            "kling",
            canonical_model(model) or model,
            "native",
            {"prompt": str(body.get("prompt") or "")},
            upstream=upstream,
        )
        return raw, job

    # --- status -------------------------------------------------------------

    def _job(self, video_id: str) -> dict[str, Any]:
        job = self.jobs.get(video_id)
        if job is None:
            raise ApiError(f"Video '{video_id}' not found", 404, "not_found")
        return job

    async def _task(self, upstream: dict[str, Any]) -> dict[str, Any]:
        """Normalized task state: status, message, result videos and audios."""
        if upstream["api"] == "legacy":
            path = upstream.get("path") or "/v1/videos/" + upstream["endpoint"]
            data = await self.client.call("GET", f"{path}/{upstream['task_id']}")
            result = data.get("task_result") or {}
            return {
                "status": data.get("task_status"),
                "message": data.get("task_status_msg"),
                "videos": result.get("videos") or [],
                "audios": result.get("audios") or [],
            }
        data = await self.client.call(
            "GET", "/tasks", params={"task_ids": upstream["task_id"]}
        )
        tasks = data.get("result") if isinstance(data, dict) else data
        task = next(
            (
                item
                for item in tasks or []
                if str(item.get("id")) == str(upstream["task_id"])
            ),
            None,
        )
        if task is None:
            return {"status": "processing", "message": None, "videos": [], "audios": []}
        outputs = task.get("outputs") or []
        return {
            "status": task.get("status"),
            "message": task.get("message"),
            "videos": [item for item in outputs if item.get("type") == "video"],
            "audios": [
                {
                    "id": item.get("id"),
                    "url_mp3": item.get("mp3_url"),
                    "url_wav": item.get("wav_url"),
                }
                for item in outputs
                if item.get("type") == "audio"
            ],
        }

    async def refresh(self, video_id: str) -> dict[str, Any]:
        job = self._job(video_id)
        if job["status"] in TERMINAL_STATUSES or job["upstream"] is None:
            # Worker jobs before their render step have nothing to poll yet.
            return job
        now = time.monotonic()
        if (
            now - self.last_polled.get(video_id, float("-inf"))
            < self.settings.provider_status_min_interval_seconds
        ):
            return job
        self.last_polled[video_id] = now
        return await self._poll(job)

    async def _poll(self, job: dict[str, Any]) -> dict[str, Any]:
        video_id = job["id"]
        task = await self._task(job["upstream"])
        status = str(task["status"] or "processing")
        if status in RUNNING:
            self.jobs.update(video_id, status="in_progress", provider_status=status)
        elif status in SUCCEEDED and (task["videos"] or task["audios"]):
            await self._complete(job, task["videos"], task["audios"])
        else:
            self.jobs.update(
                video_id,
                status="failed",
                provider_status=status,
                error={
                    "code": "upstream_error",
                    "message": task["message"]
                    or f"Kling task ended with status {status}",
                },
            )
        return self._job(video_id)

    async def _store(
        self, video_id: str, index: int, variant: str, url: str, mime_type: str
    ) -> bool:
        """Copy one result file; False while Kling cannot serve it yet."""
        if not host_allowed(url, self.settings.kling_download_host_suffixes):
            raise ApiError(
                f"Kling returned a result on an unexpected host: {url}",
                502,
                "upstream_error",
            )
        try:
            response = await stream_remote(
                url,
                headers={},
                allowed_host_suffixes=self.settings.kling_download_host_suffixes,
                transport=self.download_transport,
                timeout=self.settings.download_timeout_seconds,
                media_type=mime_type,
            )
            await self.outputs.save(
                video_id, index, variant, response.body_iterator, mime_type
            )
        except (HTTPException, httpx.HTTPError) as exc:
            logger.info(
                "Kling result for %s is not downloadable yet: %s", video_id, exc
            )
            return False
        return True

    async def _complete(
        self,
        job: dict[str, Any],
        videos: list[dict[str, Any]],
        audios: list[dict[str, Any]],
    ) -> None:
        """Kling URLs are hotlink-protected and expire after 30 days, so keep copies.

        Video-to-audio returns a video and its soundtrack; text-to-audio only audio.
        """
        video_id = job["id"]
        outputs: list[dict[str, Any]] = []
        try:
            for index in range(max(len(videos), len(audios))):
                video = videos[index] if index < len(videos) else {}
                audio = audios[index] if index < len(audios) else {}
                files = [
                    ("video", video.get("url"), "video/mp4"),
                    ("watermarked", video.get("watermark_url"), "video/mp4"),
                    ("audio", audio.get("url_mp3"), "audio/mpeg"),
                    ("audio_wav", audio.get("url_wav"), "audio/wav"),
                ]
                variants = []
                for variant, url, mime_type in files:
                    if not url:
                        continue
                    if not await self._store(video_id, index, variant, url, mime_type):
                        self.jobs.update(
                            video_id, status="in_progress", provider_status="finalizing"
                        )
                        return
                    variants.append(variant)
                outputs.append(
                    {
                        "index": index,
                        "variants": variants,
                        "mime_type": "video/mp4" if video else "audio/mpeg",
                        "stored": True,
                        "seconds": video.get("duration") or audio.get("duration_mp3"),
                        # Voices, lip sync and video-to-audio refer to Kling's video ID.
                        "kling_video_id": video.get("id"),
                    }
                )
        except ApiError as exc:
            self.jobs.update(video_id, status="failed", error=exc.to_error())
            return
        self.jobs.update(
            video_id,
            status="completed",
            provider_status="succeeded",
            progress=100,
            outputs=outputs,
            usage={"provider": "kling"},
        )

    async def get_video(self, video_id: str) -> VideoObject:
        return self.jobs.to_video(await self.refresh(video_id))

    async def delete_video(self, video_id: str) -> VideoObject:
        # Kling has no cancel endpoint; the task keeps running upstream.
        job = self._job(video_id)
        self.outputs.delete(video_id)
        self.jobs.delete(video_id)
        return self.jobs.to_video(job)

    async def stream_output(
        self,
        video_id: str,
        field: str,
        media_type: str,
        output: int = 0,
        variant: str = "video",
    ) -> StreamingResponse | JSONResponse | FileResponse:
        job = await self.refresh(video_id)
        if field != "video_url":
            return openai_error(
                "Kling models do not return a last frame", 404, "unsupported_parameter"
            )
        if job["status"] != "completed":
            return openai_error(
                f"Video is not ready (status: {job['status']})", 409, "video_not_ready"
            )
        outputs = job["outputs"] or []
        if not 0 <= output < len(outputs) or variant not in outputs[output].get(
            "variants", ["video"]
        ):
            return openai_error(
                f"Output {output} has no {variant} variant", 404, "not_found"
            )
        path = self.outputs.path(video_id, output, variant)
        if path is None:
            return openai_error("Stored result has expired", 410, "output_expired")
        media = {"audio": "audio/mpeg", "audio_wav": "audio/wav"}.get(
            variant, "video/mp4"
        )
        return FileResponse(path, media_type=media)

    # --- text-to-speech (OpenAI /v1/audio/speech) -------------------------------

    async def speech(self, body: dict[str, Any]) -> tuple[bytes, str]:
        model = canonical_model(strip_model_namespace(str(body.get("model", ""))))
        if model != "kling-tts":
            raise ContractError(
                f"{body.get('model')} cannot synthesize speech", param="model"
            )
        text = body.get("input")
        voice = body.get("voice")
        speed = float(body.get("speed", 1.0))
        language = body.get("language", "en")
        if not isinstance(text, str) or not 1 <= len(text) <= 1000:
            raise ContractError("input must have 1 to 1000 characters", param="input")
        if not isinstance(voice, str) or not voice:
            raise ContractError(
                "voice is required (a Kling TTS voice ID)", param="voice"
            )
        if not 0.8 <= speed <= 2.0:
            raise ContractError(
                "speed must be between 0.8 and 2.0",
                code="unsupported_parameter",
                param="speed",
            )
        if language not in {"zh", "en"}:
            raise ContractError(
                "language must be zh or en",
                code="unsupported_parameter",
                param="language",
            )
        data = await self.client.call(
            "POST",
            "/v1/audio/tts",
            json={
                "text": text,
                "voice_id": voice,
                "voice_language": language,
                "voice_speed": speed,
            },
        )
        clip = ((data.get("task_result") or {}).get("audios") or [{}])[0]
        url = clip.get("url")
        if not url or not host_allowed(url, self.settings.kling_download_host_suffixes):
            raise ApiError(
                "Kling text-to-speech returned no downloadable audio",
                502,
                "upstream_error",
            )
        async with httpx.AsyncClient(
            timeout=self.settings.download_timeout_seconds,
            transport=self.download_transport,
        ) as client:
            response = await client.get(url)
        if response.is_error:
            raise ApiError(
                "Kling audio download failed", 502, "upstream_error", retryable=True
            )
        return response.content, "audio/mpeg"
