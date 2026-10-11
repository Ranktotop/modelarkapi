"""Google video models (Veo 3.1 and Gemini Omni) behind the provider contract."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ..capabilities import ModelCapabilities
from ..config import Settings
from ..downloads import stream_remote
from ..errors import ApiError, openai_error
from ..ids import decode_video_id
from ..outputs import OutputStore
from ..provider_jobs import TERMINAL_STATUSES, ProviderJobStore
from ..references import ReferenceResolver
from ..schemas import VideoObject
from ..unified import UnifiedRequest, normalize_request
from ..validation import ContractError, validate
from .base import ProviderUnavailable, strip_model_namespace
from .google_backends import GoogleBackend
from .omni import build_omni_body, omni_capabilities, omni_label, parse_interaction
from .veo import build_veo_body, parse_operation, veo_capabilities, veo_label

logger = logging.getLogger(__name__)


def family_of(model: str) -> str:
    return "omni" if model.startswith("gemini-omni-") else "veo"


class GoogleProvider:
    name = "google"

    def __init__(
        self,
        settings: Settings,
        veo_backend: GoogleBackend | None,
        omni_backend: GoogleBackend | None,
        jobs: ProviderJobStore,
        outputs: OutputStore,
        references: ReferenceResolver,
        download_transport: httpx.AsyncBaseTransport | None = None,
        omni_preview_backend: GoogleBackend | None = None,
    ) -> None:
        self.settings = settings
        self.backends = {"veo": veo_backend, "omni": omni_backend}
        # GOOGLE_OMNI_BACKEND=both (SPEC 12.3): GA IDs use `omni_backend`
        # (Gemini API), `-preview` IDs this one (Vertex AI).
        self.omni_preview_backend = omni_preview_backend
        self.jobs = jobs
        self.outputs = outputs
        self.references = references
        self.download_transport = download_transport
        self.model_cache: list[dict[str, Any]] | None = None
        self.model_cache_expires_at = 0.0
        self.model_lock = asyncio.Lock()
        self.last_polled: dict[str, float] = {}

    def owns_video(self, video_id: str) -> bool:
        return video_id.startswith(("vid-veo-", "vid-omni-"))

    # --- models -----------------------------------------------------------

    def _model_backend(self, model: str) -> GoogleBackend | None:
        family = family_of(model)
        if (
            family == "omni"
            and self.omni_preview_backend
            and model.endswith("-preview")
        ):
            return self.omni_preview_backend
        return self.backends[family]

    def _capabilities(self, model: str) -> ModelCapabilities:
        family = family_of(model)
        backend = self._model_backend(model)
        assert backend is not None
        if family == "omni":
            return omni_capabilities(model, backend.name)
        return veo_capabilities(model, backend.name)

    async def list_models(self) -> list[dict[str, Any]]:
        if self.model_cache is None or time.monotonic() >= self.model_cache_expires_at:
            async with self.model_lock:
                if (
                    self.model_cache is None
                    or time.monotonic() >= self.model_cache_expires_at
                ):
                    models: list[dict[str, Any]] = []
                    veo, omni = self.backends["veo"], self.backends["omni"]
                    preview = self.omni_preview_backend
                    omni_ids = await omni.list_omni_models() if omni else []
                    if preview:
                        omni_ids = [
                            model
                            for model in omni_ids
                            if not model.endswith("-preview")
                        ] + [
                            model
                            for model in await preview.list_omni_models()
                            if model.endswith("-preview")
                        ]
                    ids = (await veo.list_veo_models() if veo else []) + omni_ids
                    for model in ids:
                        label = (
                            omni_label(model)
                            if family_of(model) == "omni"
                            else veo_label(model)
                        )
                        models.append(
                            {
                                "id": model,
                                "object": "model",
                                "owned_by": "google",
                                "name": label,
                                "capabilities": self._capabilities(model).to_dict(),
                            }
                        )
                    self.model_cache = models
                    self.model_cache_expires_at = (
                        time.monotonic() + self.settings.model_cache_ttl_seconds
                    )
        return self.model_cache or []

    async def _model(self, model: str) -> str:
        bare = strip_model_namespace(model)
        if bare not in {entry["id"] for entry in await self.list_models()}:
            raise ProviderUnavailable(f"Model '{bare}' is not available on this proxy")
        return bare

    # --- create -------------------------------------------------------------

    async def create_video(
        self, data: dict[str, Any], upload: UploadFile | None
    ) -> VideoObject:
        if upload is not None:
            raise ContractError(
                "Google models do not accept input_reference uploads; use references",
                code="unsupported_parameter",
                param="input_reference",
            )
        request = normalize_request(
            data, default_policy=self.settings.default_parameter_policy
        )
        model = await self._model(request.model)
        request.model = model
        caps = self._capabilities(model)
        request, adjustments = validate(caps, request)
        options = request.provider_options.get("google") or {}
        unknown = sorted(set(options) - set(caps.provider_options))
        if unknown:
            raise ContractError(
                f"Unsupported provider_options.google fields: {', '.join(unknown)}",
                code="unsupported_parameter",
                param="provider_options",
            )
        family = family_of(model)
        backend = self._model_backend(model)
        assert backend is not None
        previous = self._previous_interaction(request, family, backend)
        media = await self._resolve(caps, request, family)
        if family == "omni":
            interaction = await backend.start_omni(
                build_omni_body(
                    request,
                    caps,
                    media,
                    delivery_uri=backend.name == "gemini",
                    previous_interaction=previous,
                )
            )
            upstream = {
                "kind": "omni",
                "interaction": interaction["id"],
                "backend": backend.name,
            }
        else:
            operation = await backend.start_veo(
                model, build_veo_body(request, caps, media)
            )
            upstream = {
                "kind": "veo",
                "operation": operation["name"],
                "backend": backend.name,
            }
        job = self._register(
            model, request.task, request.prompt, request.params, upstream
        )
        if adjustments:
            self.jobs.update(job["id"], adjustments=adjustments)
        return self.jobs.to_video(self.jobs.get(job["id"]) or job)

    def _previous_interaction(
        self, request: UnifiedRequest, family: str, backend: GoogleBackend
    ) -> str | None:
        """Use Omni multi-turn when the base video is an Omni job of this backend.

        The reference is removed so its bytes are not uploaded again. This is
        also the only way the Gemini API edits videos for users in the EEA.
        """
        if family != "omni":
            return None
        for reference in list(request.references):
            if reference["role"] != "base_video" or not reference.get("task_id"):
                continue
            job = self.jobs.get(decode_video_id(str(reference["task_id"])))
            upstream = (job or {}).get("upstream") or {}
            if (
                job
                and upstream.get("kind") == "omni"
                and upstream.get("backend") == backend.name
            ):
                if job["status"] != "completed":
                    raise ContractError(
                        "The source job has not finished yet",
                        code="reference_unavailable",
                        param="references",
                    )
                request.references.remove(reference)
                return str(upstream["interaction"])
        return None

    async def _resolve(
        self, caps: ModelCapabilities, request: UnifiedRequest, family: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch every reference and shape it the way the model family expects."""
        slots = {slot.role: slot for slot in caps.tasks[request.task].references}
        resolved: dict[str, list[dict[str, Any]]] = {}
        backend = caps.backend
        for reference in request.references:
            role = reference["role"]
            if (
                role == "base_video"
                and backend == "gemini"
                and family == "veo"
                and not reference.get("task_id")
            ):
                raise ContractError(
                    "The Gemini API only extends Veo videos generated through this "
                    "proxy; pass the earlier job as task_id",
                    code="reference_limit",
                    param="references",
                )
            media = await self.references.fetch(reference)
            slot = slots[role]
            if slot.formats and media.mime_type not in slot.formats:
                raise ContractError(
                    f"{role} must be {' or '.join(slot.formats)}, not {media.mime_type}",
                    code="reference_limit",
                    param="references",
                )
            if slot.max_bytes and len(media.data) > slot.max_bytes:
                raise ContractError(
                    f"{role} may not exceed {slot.max_bytes} bytes",
                    code="reference_limit",
                    param="references",
                )
            content: dict[str, Any]
            if family == "omni":
                content = {
                    "type": reference["type"],
                    "mime_type": media.mime_type,
                    "data": media.base64,
                }
            elif role == "base_video" and backend == "gemini":
                content = {
                    "inlineData": {"mimeType": media.mime_type, "data": media.base64}
                }
            else:
                content = {
                    "bytesBase64Encoded": media.base64,
                    "mimeType": media.mime_type,
                }
            resolved.setdefault(role, []).append(content)
        return resolved

    def _register(
        self,
        model: str,
        task: str,
        prompt: str,
        params: dict[str, Any],
        upstream: dict[str, Any],
    ) -> dict[str, Any]:
        return self.jobs.create(
            "google",
            model,
            task,
            {"prompt": prompt, "seconds": params.get("seconds"), "params": params},
            slug=upstream["kind"],
            upstream=upstream,
        )

    async def create_native_veo(
        self, model: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        model = await self._model(model)
        backend = self.backends["veo"]
        if family_of(model) != "veo" or backend is None:
            raise ProviderUnavailable(f"Model '{model}' is not a Veo model")
        operation = await backend.start_veo(model, body)
        instance = (body.get("instances") or [{}])[0]
        job = self._register(
            model,
            "native",
            str(instance.get("prompt") or ""),
            {"seconds": (body.get("parameters") or {}).get("durationSeconds")},
            {"kind": "veo", "operation": operation["name"], "backend": backend.name},
        )
        return {**operation, "proxy_job_id": job["id"]}

    # --- status -------------------------------------------------------------

    def _job(self, video_id: str) -> dict[str, Any]:
        job = self.jobs.get(video_id)
        if job is None:
            raise ApiError(f"Video '{video_id}' not found", 404, "not_found")
        return job

    def _backend_for(self, job: dict[str, Any]) -> GoogleBackend:
        backend = self.backends[job["upstream"]["kind"]]
        preview = self.omni_preview_backend
        if (
            job["upstream"]["kind"] == "omni"
            and preview
            and job["upstream"].get("backend") == preview.name
        ):
            backend = preview
        if backend is None:
            raise ProviderUnavailable(
                f"{job['upstream']['kind']} is not configured on this proxy"
            )
        return backend

    async def refresh(self, video_id: str) -> dict[str, Any]:
        job = self._job(video_id)
        if job["status"] in TERMINAL_STATUSES:
            return job
        now = time.monotonic()
        # Status requests closer together than this reuse the stored state.
        min_interval = self.settings.provider_status_min_interval_seconds
        if now - self.last_polled.get(video_id, float("-inf")) < min_interval:
            return job
        self.last_polled[video_id] = now
        upstream = job["upstream"]
        backend = self._backend_for(job)
        if upstream["kind"] == "omni":
            result = parse_interaction(await backend.get_omni(upstream["interaction"]))
        else:
            result = parse_operation(
                await backend.poll_veo(job["model"], upstream["operation"])
            )
        if result["status"] == "in_progress":
            self.jobs.update(
                video_id,
                status="in_progress",
                provider_status=result.get("provider_status", "running"),
                progress=result.get("progress"),
            )
        elif result["status"] == "failed":
            self.jobs.update(
                video_id,
                status="failed",
                provider_status=result.get("provider_status", "done"),
                error=result["error"],
            )
        else:
            await self._complete(job, backend, result)
        return self._job(video_id)

    async def _complete(
        self, job: dict[str, Any], backend: GoogleBackend, result: dict[str, Any]
    ) -> None:
        """Store every output locally; URIs are downloaded with the backend's auth."""
        video_id = job["id"]
        outputs = []
        for index, output in enumerate(result["outputs"]):
            entry: dict[str, Any] = {
                "index": index,
                "variants": ["video"],
                "mime_type": output["mime_type"],
                "stored": True,
            }
            if output["bytes"]:
                data = base64.b64decode(output["bytes"])

                async def chunks(payload: bytes = data):
                    yield payload

                await self.outputs.save(
                    video_id, index, "video", chunks(), output["mime_type"]
                )
            else:
                # Keep a copy: Gemini deletes files after two days, and
                # extensions need the bytes of the earlier video.
                try:
                    response = await stream_remote(
                        output["uri"],
                        headers=await backend.headers(),
                        allowed_host_suffixes=self.settings.google_download_host_suffixes,
                        transport=self.download_transport,
                        timeout=self.settings.download_timeout_seconds,
                        media_type=output["mime_type"],
                    )
                    await self.outputs.save(
                        video_id,
                        index,
                        "video",
                        response.body_iterator,
                        output["mime_type"],
                    )
                except HTTPException as exc:
                    # A freshly generated file may not be downloadable yet.
                    logger.info(
                        "Output of %s is not downloadable yet: %s", video_id, exc.detail
                    )
                    self.jobs.update(
                        video_id, status="in_progress", provider_status="finalizing"
                    )
                    return
                entry["uri"] = output["uri"]
            outputs.append(entry)
        usage = {
            "provider": "google",
            "backend": backend.name,
            **(result.get("usage") or {}),
        }
        self.jobs.update(
            video_id,
            status="completed",
            provider_status=result.get("provider_status", "done"),
            progress=100,
            outputs=outputs,
            usage=usage,
        )

    async def get_video(self, video_id: str) -> VideoObject:
        return self.jobs.to_video(await self.refresh(video_id))

    async def native_operation(self, video_id: str) -> dict[str, Any]:
        job = self._job(video_id)
        backend = self._backend_for(job)
        if job["upstream"]["kind"] == "omni":
            return await backend.get_omni(job["upstream"]["interaction"])
        return await backend.poll_veo(job["model"], job["upstream"]["operation"])

    async def delete_video(self, video_id: str) -> VideoObject:
        job = self._job(video_id)
        if job["upstream"]["kind"] == "omni" and job["status"] not in TERMINAL_STATUSES:
            try:
                await self._backend_for(job).cancel_omni(job["upstream"]["interaction"])
            except (ApiError, ProviderUnavailable) as exc:
                logger.warning("Could not cancel %s upstream: %s", video_id, exc)
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
        if variant != "video":
            return openai_error(
                f"Google videos have no {variant} variant", 404, "not_found"
            )
        job = await self.refresh(video_id)
        if field != "video_url":
            return openai_error(
                "Google models do not return a last frame", 404, "unsupported_parameter"
            )
        if job["status"] != "completed":
            return openai_error(
                f"Video is not ready (status: {job['status']})", 409, "video_not_ready"
            )
        outputs = job["outputs"] or []
        if not 0 <= output < len(outputs):
            return openai_error(f"Video has no output {output}", 404, "not_found")
        path = self.outputs.path(video_id, output, "video")
        if path is None:
            return openai_error("Stored video has expired", 410, "output_expired")
        return FileResponse(path, media_type=outputs[output]["mime_type"])
