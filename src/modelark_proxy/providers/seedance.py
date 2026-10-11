"""BytePlus ModelArk (Seedance) behind the provider contract.

Everything that knows about ModelArk tasks, `content` arrays, real-human
assets, and BytePlus download hosts lives here, so the HTTP layer only routes.
"""

from __future__ import annotations

import mimetypes
import re
import time
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..asset_jobs import AssetJobManager
from ..client import ModelArkClient
from ..config import Settings
from ..errors import openai_error
from ..ids import decode_video_id
from ..media import MediaStore, upload_chunks
from ..models import (
    ADAPTIVE_RATIO_TASKS,
    ModelSpec,
    family_name,
    seedance_capabilities,
    spec_for,
)
from ..references import ReferenceResolver
from ..schemas import VideoList, VideoObject
from ..translation import TranslationError, apply_openai_format, byteplus_to_openai
from ..unified import normalize_request
from ..validation import validate

PASSTHROUGH_FIELDS = {
    "resolution",
    "ratio",
    "duration",
    "frames",
    "output_format",
    "omni_reference_task_type",
    "generate_audio",
    "watermark",
    "camera_fixed",
    "return_last_frame",
    "seed",
    "service_tier",
    "execution_expires_after",
    "priority",
    "callback_url",
    "safety_identifier",
    "draft",
}
# A final video made from a draft inherits these from the draft task; ModelArk
# rejects them when they are sent again, even with the same value.
DRAFT_INHERITED_FIELDS = (
    "prompt",
    "references",
    "reference_urls",
    "input_reference_url",
    "content",
    "duration",
    "seconds",
    "ratio",
    "aspect_ratio",
    "size",
    "seed",
    "generate_audio",
    "omni_reference_task_type",
    "frames",
    "camera_fixed",
    "draft",
)
DRAFT_FINAL_FIELDS = (
    "resolution",
    "watermark",
    "return_last_frame",
    "output_format",
    "service_tier",
    "execution_expires_after",
    "priority",
    "callback_url",
    "safety_identifier",
)

PUBLIC_ASSET_REFERENCE_FIELDS = {
    "asset_id",
    "input_reference_asset",
    "input_reference_asset_type",
    "reference_asset_ids",
    "reference_assets",
}

ASSET_ID_PATTERN = re.compile(r"^asset-[A-Za-z0-9_-]+$")
ASSET_KINDS = {
    "image": ("image_url", "reference_image"),
    "video": ("video_url", "reference_video"),
    "audio": ("audio_url", "reference_audio"),
}
VALID_REFERENCE_ROLES = {
    "image": {"reference_image", "first_frame", "last_frame"},
    "video": {"reference_video"},
    "audio": {"reference_audio"},
}


def _validate_public_reference_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise TranslationError("Reference URLs must be absolute HTTP(S) URLs")


def _asset_uri(value: str) -> str:
    asset_id = value.removeprefix("asset://")
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise TranslationError(
            "Asset IDs must use the form 'asset-…' or 'asset://asset-…'"
        )
    return f"asset://{asset_id}"


def _media_kind(media_type: str | None, default: str = "video") -> str:
    if not media_type:
        return default
    normalized = media_type.lower().strip()
    if "/" in normalized:
        normalized = normalized.split("/", 1)[0]
    if normalized not in ASSET_KINDS:
        raise TranslationError("Reference type must be image, video, or audio")
    return normalized


def _reference_content(
    url: str, media_type: str | None = None, role: str | None = None
) -> dict[str, Any]:
    if url.startswith("data:"):
        # ModelArk takes images and audio inline; videos only by URL.
        kind = _media_kind(media_type or url[5:].split(";", 1)[0])
        if kind == "video" or not url.startswith(f"data:{kind}/"):
            raise TranslationError(
                "Inline data: references are accepted for images and audio only"
            )
    else:
        _validate_public_reference_url(url)
        kind = _media_kind(media_type)
    content_type, _ = ASSET_KINDS[kind]
    selected_role = _reference_role(kind, role)
    return {
        "type": content_type,
        content_type: {"url": url},
        "role": selected_role,
    }


def _reference_role(kind: str, requested: str | None) -> str:
    default_role = ASSET_KINDS[kind][1]
    role = requested or default_role
    if role not in VALID_REFERENCE_ROLES[kind]:
        allowed = ", ".join(sorted(VALID_REFERENCE_ROLES[kind]))
        raise TranslationError(f"Invalid role for {kind}; allowed values: {allowed}")
    return role


def _asset_content(
    value: str, kind: str = "image", role: str | None = None
) -> dict[str, Any]:
    normalized_kind = _media_kind(kind, default="image")
    content_type, _ = ASSET_KINDS[normalized_kind]
    return {
        "type": content_type,
        content_type: {"url": _asset_uri(value)},
        "role": _reference_role(normalized_kind, role),
    }


def _reject_public_asset_references(data: dict[str, Any]) -> None:
    supplied_fields = sorted(PUBLIC_ASSET_REFERENCE_FIELDS.intersection(data))
    if supplied_fields:
        raise TranslationError(
            "Asset IDs are managed internally; upload a reference and set "
            "real_human=true instead (unsupported fields: "
            f"{', '.join(supplied_fields)})"
        )

    def contains_asset_uri(value: Any) -> bool:
        if isinstance(value, str):
            return value.startswith("asset://")
        if isinstance(value, list):
            return any(contains_asset_uri(item) for item in value)
        if isinstance(value, dict):
            return any(contains_asset_uri(item) for item in value.values())
        return False

    if contains_asset_uri(data.get("content")):
        raise TranslationError(
            "asset:// references are managed internally; upload a reference and "
            "set real_human=true instead"
        )


def _append_internal_asset_references(
    content: list[dict[str, Any]], assets: list[dict[str, Any]]
) -> None:
    for asset in assets:
        if not isinstance(asset, dict):
            raise TranslationError("Each internal asset reference must be an object")
        asset_id = asset.get("id")
        if not isinstance(asset_id, str):
            raise TranslationError("Each internal asset reference requires an id")
        kind = asset.get("type") or asset.get("kind") or "image"
        if not isinstance(kind, str):
            raise TranslationError("Reference asset type must be a string")
        role = asset.get("role")
        if role is not None and not isinstance(role, str):
            raise TranslationError("Reference asset role must be a string")
        content.append(_asset_content(asset_id, kind, role))


def _reference_counts(content: list[dict[str, Any]]) -> dict[str, int]:
    return {
        kind: sum(item.get("type") == f"{kind}_url" for item in content)
        for kind in ASSET_KINDS
    }


def _validate_reference_limits(
    content: list[dict[str, Any]], model: str, spec: ModelSpec
) -> None:
    counts = _reference_counts(content)
    if spec.known:
        for kind, limit in spec.reference_limits.items():
            if counts[kind] <= limit:
                continue
            if limit == 0:
                raise TranslationError(
                    f"{model} does not accept reference {kind} assets"
                )
            raise TranslationError(
                f"{model} accepts at most {limit} reference {kind} assets"
            )
        if (
            counts["audio"]
            and spec.reference_audio_requires_visual
            and not (counts["image"] or counts["video"])
        ):
            raise TranslationError(
                f"{model} requires at least one reference image or video "
                "alongside reference audio"
            )

    frame_roles = [
        item.get("role")
        for item in content
        if item.get("role") in {"first_frame", "last_frame"}
    ]
    multimodal_roles = {
        "reference_image",
        "reference_video",
        "reference_audio",
    }
    if frame_roles and any(item.get("role") in multimodal_roles for item in content):
        raise TranslationError(
            "First/last-frame generation cannot be mixed with multimodal references"
        )
    if frame_roles.count("first_frame") > 1 or frame_roles.count("last_frame") > 1:
        raise TranslationError("Only one first_frame and one last_frame are allowed")
    if "last_frame" in frame_roles and "first_frame" not in frame_roles:
        raise TranslationError("last_frame requires a first_frame reference")
    if "last_frame" in frame_roles and spec.known and not spec.supports_last_frame_role:
        raise TranslationError(f"{model} does not support last_frame references")


def _validate_choice(
    payload: dict[str, Any],
    field: str,
    allowed: tuple[str, ...] | tuple[int, ...],
    model: str,
) -> None:
    value = payload.get(field)
    if value is None or value in allowed:
        return
    supported = ", ".join(str(item) for item in allowed)
    raise TranslationError(
        f"{model} does not support {field}={value}; supported values: {supported}"
    )


def _apply_model_constraints(
    payload: dict[str, Any],
    content: list[dict[str, Any]],
    model: str,
    spec: ModelSpec,
    *,
    explicit_ratio: bool,
    explicit_duration: bool,
) -> None:
    """Validate parameters against the model and resolve its forced values.

    Seedance 2.5 pins the aspect ratio (and, when editing, the duration) to the
    input asset. Rejecting a conflicting request here turns an asynchronous
    ``InvalidParameter.TaskTypeConstraint`` failure into an immediate 400.
    """
    task_type = payload.get("omni_reference_task_type")
    if task_type is not None:
        if not spec.task_types:
            raise TranslationError(f"{model} does not support omni_reference_task_type")
        _validate_choice(payload, "omni_reference_task_type", spec.task_types, model)
    if payload.get("output_format") is not None:
        _validate_choice(payload, "output_format", spec.output_formats, model)
    if payload.get("frames") is not None and spec.known and not spec.supports_frames:
        raise TranslationError(f"{model} does not support frames; use duration")
    if spec.known:
        _validate_choice(payload, "resolution", spec.resolutions, model)
        _validate_choice(payload, "ratio", spec.ratios, model)
        _validate_choice(payload, "duration", spec.durations, model)

    roles = {item.get("role") for item in content}
    if task_type in ADAPTIVE_RATIO_TASKS and not roles & {"reference_video"}:
        raise TranslationError(
            f"omni_reference_task_type={task_type} requires at least one "
            "reference video"
        )

    frame_task = bool(roles & {"first_frame", "last_frame"})
    needs_adaptive_ratio = task_type in ADAPTIVE_RATIO_TASKS or (
        frame_task and spec.adaptive_ratio_for_frames
    )
    if needs_adaptive_ratio:
        reason = (
            f"omni_reference_task_type={task_type}"
            if task_type in ADAPTIVE_RATIO_TASKS
            else "first_frame/last_frame generation"
        )
        if explicit_ratio and payload.get("ratio") not in (None, "adaptive"):
            raise TranslationError(
                f"{model} only supports ratio=adaptive for {reason}; the output "
                "keeps the aspect ratio of the input asset"
            )
        payload["ratio"] = "adaptive"

    if task_type == "edit":
        if explicit_duration and payload.get("duration") not in (None, -1):
            raise TranslationError(
                f"{model} only supports duration=-1 for "
                "omni_reference_task_type=edit; the output keeps the duration "
                "of the edited video"
            )
        payload["duration"] = -1


def _normalize_passthrough(payload: dict[str, Any]) -> None:
    """Accept the spellings clients send and hand ModelArk its own."""
    for field in ("duration", "frames"):
        value = payload.get(field)
        if isinstance(value, str):
            try:
                payload[field] = int(value)
            except ValueError as exc:
                raise TranslationError(f"{field} must be an integer") from exc
    for field in ("resolution", "output_format", "omni_reference_task_type"):
        value = payload.get(field)
        if isinstance(value, str):
            payload[field] = value.strip().lower()


def _draft_final_payload(
    data: dict[str, Any], model: str, spec: ModelSpec
) -> dict[str, Any]:
    if spec.known and not spec.supports_draft:
        raise TranslationError(f"{model} does not support draft mode")
    inherited = [
        name for name in DRAFT_INHERITED_FIELDS if data.get(name) not in (None, "", [])
    ]
    if inherited:
        raise TranslationError(
            "A final video inherits these fields from its draft; do not send "
            f"them: {', '.join(inherited)}"
        )
    payload: dict[str, Any] = {
        "model": model,
        "content": [
            {
                "type": "draft_task",
                "draft_task": {"id": decode_video_id(str(data["draft_task_id"]))},
            }
        ],
    }
    for name in DRAFT_FINAL_FIELDS:
        if data.get(name) is not None:
            payload[name] = data[name]
    _normalize_passthrough(payload)
    if family_name(model).startswith("dreamina-seedance-2-5"):
        payload.setdefault("resolution", "1080p")
        if payload["resolution"] != "1080p":
            raise TranslationError(
                f"{model} renders the final video of a draft in 1080p only"
            )
    return payload


def build_task_payload(
    data: dict[str, Any],
    settings: Settings,
    hosted_reference: tuple[str, str, str | None] | None,
    *,
    internal_asset_references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    requested_model = data.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise TranslationError("model is required")
    model = settings.resolve_model(requested_model.strip())
    spec = spec_for(model)
    if data.get("draft_task_id") is not None:
        return _draft_final_payload(data, model, spec)
    prompt = str(data.get("prompt", "")).strip()
    content: list[dict[str, Any]] = []
    if prompt:
        content.append({"type": "text", "text": prompt})

    if hosted_reference:
        content.append(_reference_content(*hosted_reference))

    _append_internal_asset_references(content, internal_asset_references or [])

    input_url = data.get("input_reference_url")
    if isinstance(input_url, str):
        content.append(
            _reference_content(
                input_url,
                data.get("input_reference_media_type"),
                data.get("input_reference_role"),
            )
        )

    reference_urls = data.get("reference_urls", [])
    if isinstance(reference_urls, str):
        reference_urls = [reference_urls]
    if isinstance(reference_urls, list):
        for item in reference_urls:
            if isinstance(item, str):
                content.append(_reference_content(item))
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                content.append(
                    _reference_content(
                        item["url"], item.get("media_type"), item.get("role")
                    )
                )

    supplied_content = data.get("content")
    if isinstance(supplied_content, list):
        content.extend(item for item in supplied_content if isinstance(item, dict))

    _validate_reference_limits(content, model, spec)

    if not content:
        raise TranslationError("A prompt or at least one reference is required")

    payload: dict[str, Any] = {"model": model, "content": content}
    for field in PASSTHROUGH_FIELDS:
        if field in data and data[field] is not None:
            payload[field] = data[field]
    _normalize_passthrough(payload)
    if "safety_identifier" not in payload and data.get("user") is not None:
        payload["safety_identifier"] = str(data["user"])

    if "duration" not in payload and data.get("seconds") is not None:
        try:
            payload["duration"] = int(data["seconds"])
        except (TypeError, ValueError) as exc:
            raise TranslationError("seconds must be an integer") from exc
    if payload.get("draft") is not True:
        payload.pop("draft", None)
    elif spec.known and not spec.supports_draft:
        raise TranslationError(f"{model} does not support draft mode")
    else:
        payload.setdefault("resolution", "480p")
        if payload["resolution"] != "480p":
            raise TranslationError("Draft videos are rendered in 480p only")
    if spec.supports_audio:
        payload.setdefault("generate_audio", settings.default_generate_audio)
    elif "generate_audio" in payload and spec.known:
        raise TranslationError(f"{model} does not generate audio")
    apply_openai_format(payload, data.get("size"))
    _apply_model_constraints(
        payload,
        content,
        model,
        spec,
        explicit_ratio="ratio" in data,
        explicit_duration="duration" in data or "seconds" in data,
    )
    return payload


# Fields only the unified contract uses; any of them switches a request to it.
UNIFIED_MARKERS = ("references", "task", "aspect_ratio", "parameter_policy")
# Unified tasks that map onto an `omni_reference_task_type` (Seedance 2.5).
OMNI_TASKS = {"edit": "edit", "extend": "extend", "stitch": "extend"}
UNIFIED_TO_SEEDANCE_PARAMS = {
    "resolution": "resolution",
    "aspect_ratio": "ratio",
    "generate_audio": "generate_audio",
    "seed": "seed",
    "watermark": "watermark",
    "return_last_frame": "return_last_frame",
    "output_format": "output_format",
}
# Request fields the unified translation replaces with Seedance fields.
CONSUMED_FIELDS = (
    *UNIFIED_MARKERS,
    "seconds",
    "duration",
    "ratio",
    "size",
    "provider_options",
    "input_reference_url",
    "input_reference_media_type",
    "input_reference_role",
    "reference_urls",
    "omni_reference_task_type",
    *UNIFIED_TO_SEEDANCE_PARAMS,
)


def is_unified(data: dict[str, Any]) -> bool:
    seconds = data.get("seconds")
    return any(name in data for name in UNIFIED_MARKERS) or (
        isinstance(seconds, str) and seconds.strip().lower() == "auto"
    )


def _seedance_role(reference: dict[str, Any]) -> str:
    role = reference["role"]
    if role in {"first_frame", "last_frame"}:
        return role
    return f"reference_{reference['type']}"


def _local_reference_id(url: str, settings: Settings) -> str | None:
    if not settings.public_base_url:
        return None
    prefix = f"{settings.public_base_url.rstrip('/')}/media/reference/"
    return url[len(prefix) :] if url.startswith(prefix) else None


def extract_real_human_sources(
    source_data: dict[str, Any], settings: Settings
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove references marked real_human and return them for asset ingestion."""
    data = deepcopy(source_data)
    sources: list[dict[str, Any]] = []

    input_url = data.get("input_reference_url")
    if data.get("real_human") is True and isinstance(input_url, str):
        kind = _media_kind(data.get("input_reference_media_type"))
        sources.append(
            {
                "url": input_url,
                "kind": kind,
                "role": _reference_role(kind, data.get("input_reference_role")),
                "local_id": _local_reference_id(input_url, settings),
            }
        )
        data.pop("input_reference_url", None)

    references = data.get("reference_urls", [])
    if isinstance(references, list):
        ordinary: list[Any] = []
        for item in references:
            if isinstance(item, dict) and item.get("real_human") is True:
                url = item.get("url")
                if not isinstance(url, str):
                    raise TranslationError("A real-human reference requires a URL")
                _validate_public_reference_url(url)
                kind = _media_kind(item.get("media_type"))
                sources.append(
                    {
                        "url": url,
                        "kind": kind,
                        "role": _reference_role(kind, item.get("role")),
                        "local_id": _local_reference_id(url, settings),
                    }
                )
            else:
                ordinary.append(item)
        data["reference_urls"] = ordinary

    if sources and not settings.real_human_assets_configured:
        raise TranslationError(
            "Real-human processing requires BYTEPLUS_ACCESS_KEY_ID, "
            "BYTEPLUS_SECRET_ACCESS_KEY, and BYTEPLUS_ASSET_GROUP_ID"
        )
    return data, sources


def _safe_download_url(url: str, settings: Settings) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(
        hostname == suffix.lstrip(".") or hostname.endswith(suffix.lower())
        for suffix in settings.allowed_download_host_suffixes
    ):
        raise HTTPException(
            status_code=502, detail="ModelArk returned a disallowed download URL"
        )


class SeedanceProvider:
    """Seedance video generation through ModelArk content-generation tasks."""

    name = "modelark"

    def __init__(
        self,
        settings: Settings,
        ark: ModelArkClient,
        asset_jobs: AssetJobManager,
        media: MediaStore,
        download_transport: httpx.AsyncBaseTransport | None = None,
        references: ReferenceResolver | None = None,
    ) -> None:
        self.settings = settings
        self.ark = ark
        self.asset_jobs = asset_jobs
        self.media = media
        self.download_transport = download_transport
        self.references = references

    async def _reference_url(self, reference: dict[str, Any]) -> str:
        """A URL (or inline image/audio) ModelArk accepts for this reference."""
        task_id = reference.get("task_id")
        if task_id:
            source_id = decode_video_id(str(task_id))
            if source_id.startswith("cgt-"):
                task = await self.ark.get_task(source_id)
                url = (task.get("content") or {}).get("video_url")
                if task.get("status") != "succeeded" or not isinstance(url, str):
                    raise TranslationError(
                        f"Task {source_id} has no finished video to reference "
                        f"(status: {task.get('status')})"
                    )
                return url
        url = reference.get("url")
        if isinstance(url, str) and (
            url.startswith("https://")
            or (url.startswith("data:") and reference["type"] != "video")
        ):
            return url
        if self.references is None:
            raise TranslationError("This reference source is not available")
        return await self.references.public_url(reference)

    async def _from_unified(self, data: dict[str, Any]) -> dict[str, Any]:
        """Translate a unified request into the Seedance fields it maps to."""
        request = normalize_request(data)
        model = self.settings.resolve_model(request.model)
        request, _ = validate(seedance_capabilities(model), request)
        spec = spec_for(model)
        legacy = {
            key: value for key, value in data.items() if key not in CONSUMED_FIELDS
        }
        reference_urls: list[dict[str, Any]] = []
        content = list(legacy.get("content") or [])
        for reference in request.references:
            if reference["type"] not in {"image", "video", "audio"}:
                raise TranslationError(
                    f"Seedance does not accept {reference['type']} references"
                )
            role = _seedance_role(reference)
            if reference.get("asset_id"):
                # Public ModelArk assets (e.g. the digital character library).
                content.append(
                    _asset_content(str(reference["asset_id"]), reference["type"], role)
                )
                continue
            reference_urls.append(
                {
                    "url": await self._reference_url(reference),
                    "media_type": reference["type"],
                    "role": role,
                    **({"real_human": True} if reference.get("real_human") else {}),
                }
            )
        legacy["reference_urls"] = reference_urls
        if content:
            legacy["content"] = content
        if request.task in OMNI_TASKS and OMNI_TASKS[request.task] in spec.task_types:
            legacy["omni_reference_task_type"] = OMNI_TASKS[request.task]
        params = request.params
        if "seconds" in params:
            legacy["duration"] = (
                -1 if params["seconds"] == "auto" else params["seconds"]
            )
        for name, field_name in UNIFIED_TO_SEEDANCE_PARAMS.items():
            if name in params:
                legacy[field_name] = params[name]
        return legacy

    def owns_video(self, video_id: str) -> bool:
        return video_id.startswith(("cgt-", "video-rh-"))

    async def create_video(
        self, data: dict[str, Any], upload: UploadFile | None
    ) -> VideoObject:
        settings = self.settings
        _reject_public_asset_references(data)
        if is_unified(data) and data.get("draft_task_id") is None:
            data = await self._from_unified(data)
        source_task_id = data.get("input_reference_task_id")
        if source_task_id is not None:
            if not isinstance(source_task_id, str) or not source_task_id.startswith(
                "cgt-"
            ):
                raise TranslationError(
                    "input_reference_task_id must be a ModelArk task ID"
                )
            source_task = await self.ark.get_task(source_task_id)
            last_frame_url = (source_task.get("content") or {}).get("last_frame_url")
            if not isinstance(last_frame_url, str):
                raise TranslationError(
                    "Source task has no last frame; create it with return_last_frame=true"
                )
            if data.get("input_reference_url"):
                raise TranslationError(
                    "input_reference_task_id and input_reference_url cannot be combined"
                )
            data["input_reference_url"] = last_frame_url
            data["input_reference_media_type"] = "image"
            data["input_reference_role"] = "first_frame"
        hosted_reference: tuple[str, str, str | None] | None = None
        if upload:
            if not settings.public_base_url:
                raise TranslationError(
                    "PUBLIC_BASE_URL is required for uploaded references because ModelArk accepts video references only by public URL"
                )
            name, media_type = await self.media.save(
                upload_chunks(upload),
                filename=upload.filename,
                declared_type=upload.content_type,
            )
            hosted_reference = (
                f"{settings.public_base_url.rstrip('/')}/media/reference/{name}",
                media_type,
                data.get("input_reference_role"),
            )
            if data.get("real_human") is True:
                data["input_reference_url"] = hosted_reference[0]
                data["input_reference_media_type"] = hosted_reference[1]
                hosted_reference = None
        self.media.cleanup()
        data, real_human_sources = extract_real_human_sources(data, settings)
        if real_human_sources:
            return self.asset_jobs.create(data, real_human_sources)
        payload = build_task_payload(data, settings, hosted_reference)
        result = await self.ark.create_task(payload)
        now = int(time.time())
        return VideoObject(
            id=str(result["id"]),
            status="queued",
            created_at=now,
            progress=0,
            seconds=str(payload.get("duration"))
            if payload.get("duration") is not None
            else None,
            size=data.get("size"),
            model=payload["model"],
        )

    async def list_videos(self, request: Request) -> VideoList:
        allowed = {
            "page_num",
            "page_size",
            "filter.status",
            "filter.task_ids",
            "filter.model",
        }
        params: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            upstream_key = "page_size" if key == "limit" else key
            if upstream_key in allowed:
                params.append((upstream_key, value))
        try:
            page_num = next(
                (int(value) for key, value in params if key == "page_num"), None
            )
            page_size = next(
                (int(value) for key, value in params if key == "page_size"), None
            )
        except ValueError as exc:
            raise TranslationError("page_num and page_size must be integers") from exc
        if page_num is not None and page_num < 1:
            raise TranslationError("page_num must be at least 1")
        if page_size is not None and not 1 <= page_size <= 500:
            raise TranslationError("page_size must be between 1 and 500")
        result = await self.ark.list_tasks(params)
        items = result.get("items", [])
        if not isinstance(items, list):
            raise HTTPException(
                status_code=502, detail="ModelArk task list has no items array"
            )
        total = result.get("total")
        has_more = (
            page_num * page_size < total
            if all(isinstance(value, int) for value in (page_num, page_size, total))
            else None
        )
        return VideoList(
            data=[byteplus_to_openai(item) for item in items],
            total=total if isinstance(total, int) else None,
            page_num=page_num,
            page_size=page_size,
            has_more=has_more,
        )

    async def get_video(self, video_id: str) -> VideoObject:
        local = self.asset_jobs.get_video(video_id)
        if local:
            return local
        return byteplus_to_openai(await self.ark.get_task(video_id))

    async def delete_video(self, video_id: str) -> VideoObject:
        if self.asset_jobs.get_video(video_id):
            return await self.asset_jobs.cancel(video_id)
        result = await self.ark.delete_task(video_id)
        result.setdefault("id", video_id)
        result.setdefault("status", "cancelled")
        return byteplus_to_openai(result)

    async def stream_output(
        self,
        video_id: str,
        field: str,
        media_type: str,
        output: int = 0,
        variant: str = "video",
    ) -> StreamingResponse | JSONResponse:
        if variant != "video":
            return openai_error(
                f"Seedance tasks have no {variant} variant", 404, "not_found"
            )
        if output != 0:
            return openai_error("Seedance tasks have a single output", 404, "not_found")
        local = self.asset_jobs.get_video(video_id)
        if local:
            provider_id = self.asset_jobs.provider_id(video_id)
            if not provider_id:
                return openai_error(
                    f"Video is not ready (status: {local.status})",
                    409,
                    "video_not_ready",
                )
            video_id = provider_id
        task = await self.ark.get_task(video_id)
        if task.get("status") != "succeeded":
            return openai_error(
                f"Video is not ready (status: {task.get('status')})",
                409,
                "video_not_ready",
            )
        url = (task.get("content") or {}).get(field)
        if not isinstance(url, str):
            detail = f"Successful ModelArk task has no {field}"
            if field == "last_frame_url":
                detail += "; enable return_last_frame when creating the task"
            raise HTTPException(
                status_code=404,
                detail=detail,
            )
        _safe_download_url(url, self.settings)
        # Seedance 2.5 can return .mov; keep the served type in sync with it.
        guessed = mimetypes.guess_type(urlparse(url).path)[0]
        if guessed and guessed.split("/", 1)[0] == media_type.split("/", 1)[0]:
            media_type = guessed

        async def stream() -> AsyncIterator[bytes]:
            async with (
                httpx.AsyncClient(
                    timeout=self.settings.download_timeout_seconds,
                    follow_redirects=True,
                    transport=self.download_transport,
                ) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

        return StreamingResponse(stream(), media_type=media_type)
