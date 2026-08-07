from __future__ import annotations

import asyncio
import hmac
import json
import logging
import mimetypes
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .asset_jobs import AssetJobManager
from .assets import AssetAPIError, AssetClient
from .client import ModelArkClient, ModelArkError
from .config import Settings
from .media import MediaStore, UploadTooLarge
from .schemas import MediaReference, MediaReferenceList, VideoList, VideoObject
from .translation import TranslationError, apply_openai_format, byteplus_to_openai

PASSTHROUGH_FIELDS = {
    "resolution",
    "ratio",
    "duration",
    "frames",
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
}

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

logger = logging.getLogger(__name__)
REFERENCE_SIZE_LIMITS = {
    "image": 30 * 1024 * 1024,
    "video": 200 * 1024 * 1024,
    "audio": 15 * 1024 * 1024,
}


def openai_error(message: str, status: int, code: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": None,
                "code": code,
            }
        },
    )


def modelark_error_code(error: ModelArkError) -> str:
    body = error.body if isinstance(error.body, dict) else {}
    upstream_error = body.get("error", body)
    code = upstream_error.get("code") if isinstance(upstream_error, dict) else None
    return str(code) if code else "modelark_error"


async def _upload_chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await upload.read(1024 * 1024):
        yield chunk


async def parse_create_request(
    request: Request,
) -> tuple[dict[str, Any], UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        data: dict[str, Any] = {}
        upload: UploadFile | None = None
        for key, value in form.multi_items():
            if key == "input_reference" and isinstance(value, StarletteUploadFile):
                upload = value
                continue
            if isinstance(value, StarletteUploadFile):
                continue
            if key in {
                "duration",
                "frames",
                "seed",
                "execution_expires_after",
                "priority",
            }:
                try:
                    data[key] = int(value)
                except ValueError:
                    data[key] = value
            elif key in {
                "generate_audio",
                "watermark",
                "camera_fixed",
                "return_last_frame",
                "real_human",
            }:
                data[key] = str(value).lower() in {"1", "true", "yes", "on"}
            elif key in {
                "reference_urls",
                "content",
            }:
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    data[key] = value
            else:
                data[key] = value
        return data, upload
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Request body must be JSON or multipart/form-data"
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    return body, None


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


def _validate_reference_limits(content: list[dict[str, Any]]) -> None:
    counts = {
        kind: sum(item.get("type") == f"{kind}_url" for item in content)
        for kind in ASSET_KINDS
    }
    if counts["image"] > 9:
        raise TranslationError("Seedance 2.0 accepts at most 9 reference images")
    if counts["video"] > 3:
        raise TranslationError("Seedance 2.0 accepts at most 3 reference videos")
    if counts["audio"] > 3:
        raise TranslationError("Seedance 2.0 accepts at most 3 reference audio files")
    if counts["audio"] and not (counts["image"] or counts["video"]):
        raise TranslationError("Reference audio requires at least one image or video")

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

    _validate_reference_limits(content)

    if not content:
        raise TranslationError("A prompt or at least one reference is required")

    payload: dict[str, Any] = {
        "model": settings.resolve_model(requested_model.strip()),
        "content": content,
    }
    for field in PASSTHROUGH_FIELDS:
        if field in data and data[field] is not None:
            payload[field] = data[field]
    if "safety_identifier" not in payload and data.get("user") is not None:
        payload["safety_identifier"] = str(data["user"])

    if "duration" not in payload and data.get("seconds") is not None:
        try:
            payload["duration"] = int(data["seconds"])
        except (TypeError, ValueError) as exc:
            raise TranslationError("seconds must be an integer") from exc
    payload.setdefault("generate_audio", settings.default_generate_audio)
    apply_openai_format(payload, data.get("size"))
    return payload


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


def create_app(
    settings: Settings | None = None,
    *,
    ark_transport: httpx.AsyncBaseTransport | None = None,
    asset_transport: httpx.AsyncBaseTransport | None = None,
    download_transport: httpx.AsyncBaseTransport | None = None,
    validate_startup_credentials: bool = True,
) -> FastAPI:
    settings = settings or Settings()
    media = MediaStore(
        settings.media_dir, settings.max_upload_bytes, settings.media_ttl_seconds
    )
    ark = ModelArkClient(settings, ark_transport)
    assets = AssetClient(settings, asset_transport)
    model_cache: list[dict[str, Any]] | None = None
    model_cache_expires_at = 0.0
    model_cache_lock = asyncio.Lock()
    credential_state: dict[str, Any] = {
        "status": "checking" if validate_startup_credentials else "valid",
        "message": None,
        "last_checked_at": None,
        "ark_api_key": "checking" if validate_startup_credentials else "valid",
        "iam": "checking" if validate_startup_credentials else "valid",
    }
    asset_jobs = AssetJobManager(
        settings,
        assets,
        ark,
        lambda data, references: build_task_payload(
            data, settings, None, internal_asset_references=references
        ),
        media.remove,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async def cleanup_media() -> None:
            while True:
                await asyncio.sleep(settings.media_cleanup_interval_seconds)
                media.cleanup()

        async def maintain_asset_jobs() -> None:
            while True:
                if credential_state["status"] == "valid":
                    await asset_jobs.maintenance()
                await asyncio.sleep(settings.asset_maintenance_interval_seconds)

        async def refresh_credential_state() -> None:
            async def validate_ark_api_key() -> str | None:
                if not settings.ark_api_key:
                    return "ARK_API_KEY is not configured"
                try:
                    async with asyncio.timeout(
                        settings.credential_validation_timeout_seconds
                    ):
                        await ark.validate_api_key()
                except ModelArkError as exc:
                    return f"ARK_API_KEY was rejected with HTTP {exc.status_code}"
                except TimeoutError:
                    return "ARK_API_KEY validation timed out"
                except httpx.HTTPError:
                    return "ARK_API_KEY validation could not reach ModelArk"
                except Exception:
                    logger.exception("Unexpected ARK_API_KEY validation failure")
                    return "ARK_API_KEY validation failed unexpectedly"
                return None

            async def validate_iam_credentials() -> str | None:
                if not settings.byteplus_access_key_id:
                    return "BYTEPLUS_ACCESS_KEY_ID is not configured"
                if not settings.byteplus_secret_access_key:
                    return "BYTEPLUS_SECRET_ACCESS_KEY is not configured"
                try:
                    async with asyncio.timeout(
                        settings.credential_validation_timeout_seconds
                    ):
                        await assets.validate_management_access()
                except AssetAPIError:
                    return (
                        "BYTEPLUS_ACCESS_KEY_ID/BYTEPLUS_SECRET_ACCESS_KEY were "
                        "rejected by the ModelArk management API"
                    )
                except TimeoutError:
                    return "IAM credential validation timed out"
                except httpx.HTTPError:
                    return (
                        "IAM credential validation could not reach the ModelArk "
                        "management API"
                    )
                except Exception:
                    logger.exception("Unexpected IAM credential validation failure")
                    return "IAM credential validation failed unexpectedly"
                return None

            ark_error, iam_error = await asyncio.gather(
                validate_ark_api_key(), validate_iam_credentials()
            )
            errors = [error for error in (ark_error, iam_error) if error]
            credential_state.update(
                status="invalid" if errors else "valid",
                message="; ".join(errors) if errors else None,
                last_checked_at=datetime.now(UTC).isoformat(),
                ark_api_key="invalid" if ark_error else "valid",
                iam="invalid" if iam_error else "valid",
            )
            if errors:
                logger.warning("ModelArk credentials are invalid: %s", "; ".join(errors))

        async def maintain_credential_state() -> None:
            while True:
                await asyncio.sleep(
                    settings.credential_validation_interval_seconds
                )
                await refresh_credential_state()

        cleanup_task: asyncio.Task[None] | None = None
        asset_task: asyncio.Task[None] | None = None
        credential_task: asyncio.Task[None] | None = None
        try:
            if validate_startup_credentials:
                await refresh_credential_state()
            media.cleanup()
            cleanup_task = asyncio.create_task(cleanup_media())
            asset_task = asyncio.create_task(maintain_asset_jobs())
            if validate_startup_credentials:
                credential_task = asyncio.create_task(maintain_credential_state())
            yield
        finally:
            if cleanup_task is not None:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
            if asset_task is not None:
                asset_task.cancel()
                with suppress(asyncio.CancelledError):
                    await asset_task
            if credential_task is not None:
                credential_task.cancel()
                with suppress(asyncio.CancelledError):
                    await credential_task
            await asset_jobs.close()
            await assets.close()
            await ark.close()

    app = FastAPI(
        title="ModelArk OpenAI Video Proxy", version="0.2.0", lifespan=lifespan
    )
    app.state.settings = settings
    app.state.ark = ark
    app.state.assets = assets
    app.state.asset_jobs = asset_jobs
    app.state.credential_state = credential_state

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if settings.proxy_api_key and not request.url.path.startswith(
            ("/health", "/media/reference/")
        ):
            authorization = request.headers.get("authorization", "")
            expected = f"Bearer {settings.proxy_api_key}"
            if not hmac.compare_digest(authorization, expected):
                response = openai_error("Invalid API key", 401, "invalid_api_key")
                response.headers["WWW-Authenticate"] = "Bearer"
                return response
        if (
            not request.url.path.startswith(("/health", "/media/reference/"))
            and credential_state["status"] != "valid"
        ):
            message = credential_state["message"] or "validation is still pending"
            return openai_error(
                f"ModelArk credentials are currently invalid: {message}",
                503,
                "upstream_credentials_invalid",
            )
        try:
            return await call_next(request)
        except ModelArkError as exc:
            return openai_error(str(exc), exc.status_code, modelark_error_code(exc))
        except AssetAPIError as exc:
            return openai_error(str(exc), 502, "modelark_asset_error")
        except TranslationError as exc:
            return openai_error(str(exc), 400, "invalid_request")
        except UploadTooLarge as exc:
            return openai_error(str(exc), 413, "upload_too_large")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "credentials": deepcopy(credential_state)}

    @app.get("/v1/models")
    @app.get("/models", include_in_schema=False)
    async def list_models() -> dict[str, Any]:
        nonlocal model_cache, model_cache_expires_at
        if not settings.model_management_configured:
            raise HTTPException(
                status_code=503,
                detail="Model discovery requires BytePlus access-key credentials",
            )
        now = time.monotonic()
        if model_cache is None or now >= model_cache_expires_at:
            async with model_cache_lock:
                now = time.monotonic()
                if model_cache is None or now >= model_cache_expires_at:
                    model_cache = await assets.list_available_seedance_models()
                    model_cache_expires_at = now + settings.model_cache_ttl_seconds
        return {
            "object": "list",
            "data": [
                {
                    "id": model["id"],
                    "object": "model",
                    "owned_by": "modelark",
                    "name": model["label"],
                    "capabilities": model["capabilities"],
                }
                for model in model_cache
            ],
        }

    @app.get("/v1/real-human/configuration")
    @app.get("/real-human/configuration", include_in_schema=False)
    async def real_human_configuration() -> dict[str, Any]:
        if not settings.real_human_assets_configured:
            return {"configured": False, "verified": False}
        result = await assets.list_asset_groups()
        items = result.get("Items", [])
        matched = next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and item.get("Id") == settings.byteplus_asset_group_id
            ),
            None,
        )
        return {
            "configured": True,
            "verified": matched is not None,
            "group_id": settings.byteplus_asset_group_id,
            "project_name": settings.byteplus_project_name,
            "group_type": matched.get("GroupType") if matched else None,
        }

    @app.get("/media/reference/{name}", include_in_schema=False)
    async def reference_media(name: str):
        path = media.resolve(name)
        if not path:
            raise HTTPException(status_code=404, detail="Reference not found")
        media_type = mimetypes.guess_type(path.name)[0]
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.post("/v1/media/references", response_model=MediaReferenceList)
    async def upload_references(request: Request) -> MediaReferenceList:
        if not settings.public_base_url:
            raise TranslationError(
                "PUBLIC_BASE_URL is required for uploaded references"
            )
        form = await request.form()
        uploads = [
            value
            for _, value in form.multi_items()
            if isinstance(value, StarletteUploadFile)
        ]
        if not uploads:
            raise TranslationError("At least one reference file is required")
        if len(uploads) > 15:
            raise TranslationError("At most 15 reference files are allowed per upload")

        saved: list[str] = []
        references: list[MediaReference] = []
        try:
            for upload in uploads:
                name, media_type = await media.save(
                    _upload_chunks(upload),
                    filename=upload.filename,
                    declared_type=upload.content_type,
                )
                saved.append(name)
                kind = media_type.split("/", 1)[0]
                path = media.resolve(name)
                size_limit = REFERENCE_SIZE_LIMITS[kind]
                if path and path.stat().st_size > size_limit:
                    raise UploadTooLarge(
                        f"{kind.capitalize()} reference exceeds {size_limit} bytes"
                    )
                references.append(
                    MediaReference(
                        id=name,
                        url=(
                            f"{settings.public_base_url.rstrip('/')}"
                            f"/media/reference/{name}"
                        ),
                        media_type=media_type,
                        kind=kind,
                        filename=upload.filename,
                        expires_at=int(time.time()) + settings.media_ttl_seconds,
                    )
                )
        except Exception:
            for name in saved:
                media.remove(name)
            raise
        return MediaReferenceList(data=references)

    @app.delete("/v1/media/references/{reference_id}")
    async def delete_reference(reference_id: str) -> dict[str, Any]:
        return {"id": reference_id, "deleted": media.remove(reference_id)}

    async def create_video(request: Request) -> VideoObject:
        data, upload = await parse_create_request(request)
        _reject_public_asset_references(data)
        source_task_id = data.get("input_reference_task_id")
        if source_task_id is not None:
            if not isinstance(source_task_id, str) or not source_task_id.startswith(
                "cgt-"
            ):
                raise TranslationError(
                    "input_reference_task_id must be a ModelArk task ID"
                )
            source_task = await ark.get_task(source_task_id)
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
            name, media_type = await media.save(
                _upload_chunks(upload),
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
        media.cleanup()
        data, real_human_sources = extract_real_human_sources(data, settings)
        if real_human_sources:
            return asset_jobs.create(data, real_human_sources)
        payload = build_task_payload(data, settings, hosted_reference)
        result = await ark.create_task(payload)
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

    app.add_api_route(
        "/v1/videos", create_video, methods=["POST"], response_model=VideoObject
    )
    app.add_api_route(
        "/videos",
        create_video,
        methods=["POST"],
        response_model=VideoObject,
        include_in_schema=False,
    )

    async def list_videos(request: Request) -> VideoList:
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
        result = await ark.list_tasks(params)
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

    app.add_api_route(
        "/v1/videos", list_videos, methods=["GET"], response_model=VideoList
    )
    app.add_api_route(
        "/videos",
        list_videos,
        methods=["GET"],
        response_model=VideoList,
        include_in_schema=False,
    )

    async def get_video(video_id: str) -> VideoObject:
        local = asset_jobs.get_video(video_id)
        if local:
            return local
        return byteplus_to_openai(await ark.get_task(video_id))

    app.add_api_route(
        "/v1/videos/{video_id}", get_video, methods=["GET"], response_model=VideoObject
    )
    app.add_api_route(
        "/videos/{video_id}",
        get_video,
        methods=["GET"],
        response_model=VideoObject,
        include_in_schema=False,
    )

    async def delete_video(video_id: str) -> VideoObject:
        if asset_jobs.get_video(video_id):
            return await asset_jobs.cancel(video_id)
        result = await ark.delete_task(video_id)
        result.setdefault("id", video_id)
        result.setdefault("status", "cancelled")
        return byteplus_to_openai(result)

    app.add_api_route(
        "/v1/videos/{video_id}",
        delete_video,
        methods=["DELETE"],
        response_model=VideoObject,
    )
    app.add_api_route(
        "/videos/{video_id}",
        delete_video,
        methods=["DELETE"],
        response_model=VideoObject,
        include_in_schema=False,
    )

    async def stream_task_output(
        video_id: str, field: str, media_type: str
    ) -> StreamingResponse | JSONResponse:
        local = asset_jobs.get_video(video_id)
        if local:
            provider_id = asset_jobs.provider_id(video_id)
            if not provider_id:
                return openai_error(
                    f"Video is not ready (status: {local.status})",
                    409,
                    "video_not_ready",
                )
            video_id = provider_id
        task = await ark.get_task(video_id)
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
        _safe_download_url(url, settings)

        async def stream() -> AsyncIterator[bytes]:
            async with (
                httpx.AsyncClient(
                    timeout=settings.download_timeout_seconds,
                    follow_redirects=True,
                    transport=download_transport,
                ) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

        return StreamingResponse(stream(), media_type=media_type)

    async def video_content(video_id: str):
        return await stream_task_output(video_id, "video_url", "video/mp4")

    async def last_frame_content(video_id: str):
        return await stream_task_output(video_id, "last_frame_url", "image/png")

    app.add_api_route("/v1/videos/{video_id}/content", video_content, methods=["GET"])
    app.add_api_route(
        "/videos/{video_id}/content",
        video_content,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_api_route(
        "/v1/videos/{video_id}/last_frame", last_frame_content, methods=["GET"]
    )
    app.add_api_route(
        "/videos/{video_id}/last_frame",
        last_frame_content,
        methods=["GET"],
        include_in_schema=False,
    )

    return app
