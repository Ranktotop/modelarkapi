"""Turns any reference source into bytes (docs/SPEC.md, section 7).

Providers that need the content itself (Google) get the same sources as
providers that fetch URLs themselves: https URLs, data: URIs, uploads, the
proxy's own media URLs, and outputs of earlier jobs.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .downloads import safe_fetch, system_resolver
from .ids import decode_video_id
from .media import REFERENCE_SIZE_LIMITS, MediaStore, detect_media_type
from .outputs import OutputStore
from .provider_jobs import ProviderJobStore
from .validation import ContractError


@dataclass(frozen=True)
class ResolvedMedia:
    data: bytes
    mime_type: str

    @property
    def base64(self) -> str:
        return base64.b64encode(self.data).decode()


def _unavailable(message: str) -> ContractError:
    return ContractError(message, code="reference_unavailable", param="references")


def _limit(message: str) -> ContractError:
    return ContractError(message, code="reference_limit", param="references")


class ReferenceResolver:
    def __init__(
        self,
        settings: Settings,
        media: MediaStore,
        jobs: ProviderJobStore,
        outputs: OutputStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Callable[[str], list[str]] = system_resolver,
    ) -> None:
        self.settings = settings
        self.media = media
        self.jobs = jobs
        self.outputs = outputs
        self.transport = transport
        self.resolver = resolver

    def _own_media_name(self, url: str) -> str | None:
        if not self.settings.public_base_url:
            return None
        prefix = f"{self.settings.public_base_url.rstrip('/')}/media/reference/"
        return url[len(prefix) :] if url.startswith(prefix) else None

    def is_own_media(self, url: str) -> bool:
        return self._own_media_name(url) is not None

    def _read_upload(self, name: str) -> bytes:
        path = self.media.resolve(name) or self.media.resolve(name.removeprefix("ref-"))
        if path is None:
            raise _unavailable(f"Upload '{name}' does not exist or has expired")
        return path.read_bytes()

    def _read_job_output(self, reference: dict[str, Any]) -> bytes:
        job_id = decode_video_id(str(reference["task_id"]))
        job = self.jobs.get(job_id)
        index = int(reference.get("output") or 0)
        outputs = (job or {}).get("outputs") or []
        if not job or job["status"] != "completed" or not 0 <= index < len(outputs):
            raise _unavailable(f"Job '{job_id}' has no finished output {index}")
        path = self.outputs.path(job_id, index, "video")
        if path is None:
            raise _unavailable(
                f"The output of job '{job_id}' is not stored by the proxy"
            )
        return path.read_bytes()

    async def fetch(self, reference: dict[str, Any]) -> ResolvedMedia:
        kind = reference["type"]
        limit = REFERENCE_SIZE_LIMITS.get(kind)
        if limit is None:
            raise _unavailable(f"{kind} references cannot be used as file content")
        url = reference.get("url")
        if reference.get("asset_id"):
            raise _unavailable("This provider cannot use asset references")
        if reference.get("upload_id"):
            data = self._read_upload(str(reference["upload_id"]))
        elif reference.get("task_id"):
            data = self._read_job_output(reference)
        elif isinstance(url, str) and url.startswith("data:"):
            header, _, payload = url.partition(",")
            if ";base64" not in header:
                raise _unavailable("data: references must be base64 encoded")
            if len(payload) * 3 // 4 > self.settings.max_inline_reference_bytes:
                raise _limit(
                    f"Inline references may not exceed "
                    f"{self.settings.max_inline_reference_bytes} bytes"
                )
            try:
                data = base64.b64decode(payload, validate=True)
            except binascii.Error as exc:
                raise _unavailable("data: reference is not valid base64") from exc
        elif isinstance(url, str) and (name := self._own_media_name(url)):
            data = self._read_upload(name)
        elif isinstance(url, str):
            data, _ = await safe_fetch(
                url,
                max_bytes=limit,
                transport=self.transport,
                resolver=self.resolver,
                timeout=self.settings.download_timeout_seconds,
            )
        else:
            raise _unavailable("Reference has no usable source")
        if len(data) > limit:
            raise _limit(f"{kind} references may not exceed {limit} bytes")
        try:
            mime_type, _ = detect_media_type(data[:64], None, None)
        except ValueError as exc:
            raise _limit(f"Reference content is not a supported {kind} file") from exc
        if mime_type.split("/", 1)[0] != kind:
            raise _limit(f"Reference declared as {kind} contains {mime_type}")
        return ResolvedMedia(data=data, mime_type=mime_type)
