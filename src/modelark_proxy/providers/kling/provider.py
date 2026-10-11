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
    MODELS,
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
        request = normalize_request(data)
        model_id = canonical_model(strip_model_namespace(request.model))
        if model_id is None:
            raise ProviderUnavailable(
                f"Model '{request.model}' is not available on this proxy"
            )
        request.model = model_id
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
        """Normalized task state: status, message, and result videos."""
        if upstream["api"] == "legacy":
            data = await self.client.call(
                "GET",
                f"{upstream.get('path') or '/v1/videos/' + upstream['endpoint']}"
                f"/{upstream['task_id']}",
            )
            result = data.get("task_result") or {}
            return {
                "status": data.get("task_status"),
                "message": data.get("task_status_msg"),
                "videos": result.get("videos") or [],
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
            return {"status": "processing", "message": None, "videos": []}
        return {
            "status": task.get("status"),
            "message": task.get("message"),
            "videos": [
                item
                for item in task.get("outputs") or []
                if item.get("type") == "video"
            ],
        }

    async def refresh(self, video_id: str) -> dict[str, Any]:
        job = self._job(video_id)
        if job["status"] in TERMINAL_STATUSES:
            return job
        now = time.monotonic()
        if (
            now - self.last_polled.get(video_id, float("-inf"))
            < self.settings.provider_status_min_interval_seconds
        ):
            return job
        self.last_polled[video_id] = now
        task = await self._task(job["upstream"])
        status = str(task["status"] or "processing")
        if status in RUNNING:
            self.jobs.update(video_id, status="in_progress", provider_status=status)
        elif status in SUCCEEDED and task["videos"]:
            await self._complete(job, task["videos"])
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

    async def _complete(
        self, job: dict[str, Any], videos: list[dict[str, Any]]
    ) -> None:
        """Kling URLs are hotlink-protected and expire after 30 days, so keep copies."""
        video_id = job["id"]
        outputs = []
        for index, video in enumerate(videos):
            variants = ["video"]
            for variant, url in (
                ("video", video.get("url")),
                ("watermarked", video.get("watermark_url")),
            ):
                if not url:
                    continue
                if not host_allowed(url, self.settings.kling_download_host_suffixes):
                    self.jobs.update(
                        video_id,
                        status="failed",
                        error={
                            "code": "upstream_error",
                            "message": f"Kling returned a result on an unexpected host: {url}",
                        },
                    )
                    return
                try:
                    response = await stream_remote(
                        url,
                        headers={},
                        allowed_host_suffixes=self.settings.kling_download_host_suffixes,
                        transport=self.download_transport,
                        timeout=self.settings.download_timeout_seconds,
                        media_type="video/mp4",
                    )
                    await self.outputs.save(
                        video_id, index, variant, response.body_iterator, "video/mp4"
                    )
                except (HTTPException, httpx.HTTPError) as exc:
                    logger.info(
                        "Kling result for %s is not downloadable yet: %s", video_id, exc
                    )
                    self.jobs.update(
                        video_id, status="in_progress", provider_status="finalizing"
                    )
                    return
                if variant == "watermarked":
                    variants.append("watermarked")
            outputs.append(
                {
                    "index": index,
                    "variants": variants,
                    "mime_type": "video/mp4",
                    "stored": True,
                    "seconds": video.get("duration"),
                    # Voices and lip sync refer to Kling's own video ID.
                    "kling_video_id": video.get("id"),
                }
            )
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
        self, video_id: str, field: str, media_type: str, output: int = 0
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
        path = self.outputs.path(video_id, output, "video")
        if path is None:
            return openai_error(f"Video has no output {output}", 404, "not_found")
        return FileResponse(path, media_type="video/mp4")
