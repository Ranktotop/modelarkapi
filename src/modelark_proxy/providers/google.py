"""Google video models (Veo 3.1; Omni follows in T12) behind the provider contract."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx
from fastapi import UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ..capabilities import ModelCapabilities
from ..config import Settings
from ..downloads import stream_remote
from ..errors import ApiError, openai_error
from ..outputs import OutputStore
from ..provider_jobs import TERMINAL_STATUSES, ProviderJobStore
from ..references import ReferenceResolver
from ..schemas import VideoObject
from ..unified import UnifiedRequest, normalize_request
from ..validation import ContractError, validate
from .base import ProviderUnavailable, strip_model_namespace
from .google_backends import GoogleBackend
from .veo import build_veo_body, parse_operation, veo_capabilities, veo_label


class GoogleProvider:
    name = "google"

    def __init__(
        self,
        settings: Settings,
        veo_backend: GoogleBackend | None,
        jobs: ProviderJobStore,
        outputs: OutputStore,
        references: ReferenceResolver,
        download_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.veo_backend = veo_backend
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

    async def list_models(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self.model_cache is None or now >= self.model_cache_expires_at:
            async with self.model_lock:
                if (
                    self.model_cache is None
                    or time.monotonic() >= self.model_cache_expires_at
                ):
                    models: list[dict[str, Any]] = []
                    if self.veo_backend is not None:
                        backend = self.veo_backend.name
                        for model in await self.veo_backend.list_veo_models():
                            models.append(
                                {
                                    "id": model,
                                    "object": "model",
                                    "owned_by": "google",
                                    "name": veo_label(model),
                                    "capabilities": veo_capabilities(
                                        model, backend
                                    ).to_dict(),
                                }
                            )
                    self.model_cache = models
                    self.model_cache_expires_at = (
                        time.monotonic() + self.settings.model_cache_ttl_seconds
                    )
        return self.model_cache or []

    async def _veo_model(self, model: str) -> str:
        bare = strip_model_namespace(model)
        if self.veo_backend is None or bare not in {
            entry["id"] for entry in await self.list_models()
        }:
            raise ProviderUnavailable(f"Model '{bare}' is not available on this proxy")
        return bare

    async def create_video(
        self, data: dict[str, Any], upload: UploadFile | None
    ) -> VideoObject:
        if upload is not None:
            raise ContractError(
                "Google models do not accept input_reference uploads yet; "
                "use references",
                code="unsupported_parameter",
                param="input_reference",
            )
        request = normalize_request(data)
        model = await self._veo_model(request.model)
        assert self.veo_backend is not None
        caps = veo_capabilities(model, self.veo_backend.name)
        request, adjustments = validate(caps, request)
        options = request.provider_options.get("google") or {}
        unknown = sorted(set(options) - set(caps.provider_options))
        if unknown:
            raise ContractError(
                f"Unsupported provider_options.google fields: {', '.join(unknown)}",
                code="unsupported_parameter",
                param="provider_options",
            )
        images = await self._resolve_images(caps, request)
        operation = await self.veo_backend.start_veo(
            model, build_veo_body(request, caps, images)
        )
        job = self._register(
            model, request.task, request.prompt, request.params, operation
        )
        if adjustments:
            self.jobs.update(job["id"], adjustments=adjustments)
        return self.jobs.to_video(self.jobs.get(job["id"]) or job)

    async def _resolve_images(
        self, caps: ModelCapabilities, request: UnifiedRequest
    ) -> dict[str, list[dict[str, str]]]:
        slots = {slot.role: slot for slot in caps.tasks[request.task].references}
        images: dict[str, list[dict[str, str]]] = {}
        backend = caps.backend
        for reference in request.references:
            if (
                reference["role"] == "base_video"
                and backend == "gemini"
                and not reference.get("task_id")
            ):
                raise ContractError(
                    "The Gemini API only extends Veo videos generated through this "
                    "proxy; pass the earlier job as task_id",
                    code="reference_limit",
                    param="references",
                )
            media = await self.references.fetch(reference)
            slot = slots[reference["role"]]
            if slot.formats and media.mime_type not in slot.formats:
                raise ContractError(
                    f"{reference['role']} must be {' or '.join(slot.formats)}, "
                    f"not {media.mime_type}",
                    code="reference_limit",
                    param="references",
                )
            if slot.max_bytes and len(media.data) > slot.max_bytes:
                raise ContractError(
                    f"{reference['role']} may not exceed {slot.max_bytes} bytes",
                    code="reference_limit",
                    param="references",
                )
            if reference["role"] == "base_video" and backend == "gemini":
                content: dict[str, Any] = {
                    "inlineData": {"mimeType": media.mime_type, "data": media.base64}
                }
            else:
                content = {
                    "bytesBase64Encoded": media.base64,
                    "mimeType": media.mime_type,
                }
            images.setdefault(reference["role"], []).append(content)
        return images

    def _register(
        self,
        model: str,
        task: str,
        prompt: str,
        params: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        assert self.veo_backend is not None
        return self.jobs.create(
            "google",
            model,
            task,
            {"prompt": prompt, "seconds": params.get("seconds"), "params": params},
            slug="veo",
            upstream={
                "kind": "veo",
                "operation": operation["name"],
                "backend": self.veo_backend.name,
            },
        )

    async def create_native_veo(
        self, model: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        model = await self._veo_model(model)
        assert self.veo_backend is not None
        operation = await self.veo_backend.start_veo(model, body)
        instance = (body.get("instances") or [{}])[0]
        job = self._register(
            model,
            "native",
            str(instance.get("prompt") or ""),
            {"seconds": (body.get("parameters") or {}).get("durationSeconds")},
            operation,
        )
        return {**operation, "proxy_job_id": job["id"]}

    def _job(self, video_id: str) -> dict[str, Any]:
        job = self.jobs.get(video_id)
        if job is None:
            raise ApiError(f"Video '{video_id}' not found", 404, "not_found")
        return job

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
        upstream = job["upstream"] or {}
        if self.veo_backend is None:
            raise ProviderUnavailable("Veo is not configured on this proxy")
        operation = await self.veo_backend.poll_veo(job["model"], upstream["operation"])
        result = parse_operation(operation)
        if result["status"] == "in_progress":
            self.jobs.update(
                video_id,
                status="in_progress",
                provider_status="running",
                progress=result.get("progress"),
            )
        elif result["status"] == "failed":
            self.jobs.update(
                video_id, status="failed", provider_status="done", error=result["error"]
            )
        else:
            outputs = []
            expires_at = job["expires_at"]
            for index, output in enumerate(result["outputs"]):
                entry = {
                    "index": index,
                    "variants": ["video"],
                    "mime_type": output["mime_type"],
                }
                if output["bytes"]:
                    data = base64.b64decode(output["bytes"])

                    async def chunks(payload: bytes = data):
                        yield payload

                    await self.outputs.save(
                        video_id, index, "video", chunks(), output["mime_type"]
                    )
                    entry["stored"] = True
                else:
                    # Keep a copy: Gemini deletes files after two days, and
                    # extensions need the bytes of the earlier video.
                    assert self.veo_backend is not None
                    response = await stream_remote(
                        output["uri"],
                        headers=await self.veo_backend.headers(),
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
                    entry["stored"] = True
                    entry["uri"] = output["uri"]
                outputs.append(entry)
            self.jobs.update(
                video_id,
                status="completed",
                provider_status="done",
                progress=100,
                outputs=outputs,
                expires_at=expires_at,
            )
        return self._job(video_id)

    async def get_video(self, video_id: str) -> VideoObject:
        return self.jobs.to_video(await self.refresh(video_id))

    async def native_operation(self, video_id: str) -> dict[str, Any]:
        job = self._job(video_id)
        if self.veo_backend is None:
            raise ProviderUnavailable("Veo is not configured on this proxy")
        return await self.veo_backend.poll_veo(
            job["model"], job["upstream"]["operation"]
        )

    async def delete_video(self, video_id: str) -> VideoObject:
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
                "Google models do not return a last frame", 404, "unsupported_parameter"
            )
        if job["status"] != "completed":
            return openai_error(
                f"Video is not ready (status: {job['status']})", 409, "video_not_ready"
            )
        outputs = job["outputs"] or []
        if not 0 <= output < len(outputs):
            return openai_error(f"Video has no output {output}", 404, "not_found")
        entry = outputs[output]
        if entry.get("stored"):
            path = self.outputs.path(video_id, output, "video")
            if path is None:
                return openai_error("Stored video has expired", 410, "output_expired")
            return FileResponse(path, media_type=entry["mime_type"])
        assert self.veo_backend is not None
        return await stream_remote(
            entry["uri"],
            headers=await self.veo_backend.headers(),
            allowed_host_suffixes=self.settings.google_download_host_suffixes,
            transport=self.download_transport,
            timeout=self.settings.download_timeout_seconds,
            media_type=entry["mime_type"],
        )
