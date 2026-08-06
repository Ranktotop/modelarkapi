from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .client import ModelArkClient, ModelArkError
from .config import Settings
from .media import MediaStore, UploadTooLarge
from .schemas import VideoObject
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

ASSET_ID_PATTERN = re.compile(r"^asset-[A-Za-z0-9_-]+$")
ASSET_KINDS = {
    "image": ("image_url", "reference_image"),
    "video": ("video_url", "reference_video"),
    "audio": ("audio_url", "reference_audio"),
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
            }:
                data[key] = str(value).lower() in {"1", "true", "yes", "on"}
            elif key in {
                "reference_urls",
                "reference_asset_ids",
                "reference_assets",
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


def _reference_content(url: str, media_type: str | None = None) -> dict[str, Any]:
    _validate_public_reference_url(url)
    kind = _media_kind(media_type)
    content_type, role = ASSET_KINDS[kind]
    return {"type": content_type, content_type: {"url": url}, "role": role}


def _asset_content(value: str, kind: str = "image") -> dict[str, Any]:
    normalized_kind = _media_kind(kind, default="image")
    content_type, role = ASSET_KINDS[normalized_kind]
    return {
        "type": content_type,
        content_type: {"url": _asset_uri(value)},
        "role": role,
    }


def _append_asset_references(
    content: list[dict[str, Any]], data: dict[str, Any]
) -> None:
    single_asset = data.get("input_reference_asset") or data.get("asset_id")
    if isinstance(single_asset, str):
        content.append(
            _asset_content(
                single_asset, str(data.get("input_reference_asset_type", "image"))
            )
        )

    asset_ids = data.get("reference_asset_ids", [])
    if isinstance(asset_ids, str):
        asset_ids = [asset_ids]
    if isinstance(asset_ids, list):
        for asset_id in asset_ids:
            if not isinstance(asset_id, str):
                raise TranslationError("reference_asset_ids must contain only strings")
            content.append(_asset_content(asset_id))

    assets = data.get("reference_assets", [])
    if isinstance(assets, dict):
        assets = [assets]
    if not isinstance(assets, list):
        raise TranslationError("reference_assets must be an array")
    for asset in assets:
        if not isinstance(asset, dict):
            raise TranslationError("Each reference_assets entry must be an object")
        asset_id = asset.get("id") or asset.get("asset_id")
        if not isinstance(asset_id, str):
            raise TranslationError("Each reference asset requires an id")
        kind = asset.get("type") or asset.get("kind") or "image"
        if not isinstance(kind, str):
            raise TranslationError("Reference asset type must be a string")
        content.append(_asset_content(asset_id, kind))


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


def build_task_payload(
    data: dict[str, Any], settings: Settings, hosted_reference: tuple[str, str] | None
) -> dict[str, Any]:
    prompt = str(data.get("prompt", "")).strip()
    content: list[dict[str, Any]] = []
    if prompt:
        content.append({"type": "text", "text": prompt})

    if hosted_reference:
        content.append(_reference_content(*hosted_reference))

    _append_asset_references(content, data)

    input_url = data.get("input_reference_url")
    if isinstance(input_url, str):
        content.append(
            _reference_content(input_url, data.get("input_reference_media_type"))
        )

    reference_urls = data.get("reference_urls", [])
    if isinstance(reference_urls, str):
        reference_urls = [reference_urls]
    if isinstance(reference_urls, list):
        for item in reference_urls:
            if isinstance(item, str):
                content.append(_reference_content(item))
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                content.append(_reference_content(item["url"], item.get("media_type")))

    supplied_content = data.get("content")
    if isinstance(supplied_content, list):
        content.extend(item for item in supplied_content if isinstance(item, dict))

    _validate_reference_limits(content)

    if not content:
        raise TranslationError("A prompt or at least one reference is required")

    payload: dict[str, Any] = {
        "model": settings.resolve_model(data.get("model")),
        "content": content,
    }
    for field in PASSTHROUGH_FIELDS:
        if field in data and data[field] is not None:
            payload[field] = data[field]

    if "duration" not in payload and data.get("seconds") is not None:
        try:
            payload["duration"] = int(data["seconds"])
        except (TypeError, ValueError) as exc:
            raise TranslationError("seconds must be an integer") from exc
    payload.setdefault("generate_audio", settings.default_generate_audio)
    apply_openai_format(payload, data.get("size"))
    return payload


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
    download_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings()
    media = MediaStore(
        settings.media_dir, settings.max_upload_bytes, settings.media_ttl_seconds
    )
    ark = ModelArkClient(settings, ark_transport)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        media.cleanup()
        yield
        await ark.close()

    app = FastAPI(
        title="ModelArk OpenAI Video Proxy", version="0.1.0", lifespan=lifespan
    )
    app.state.settings = settings
    app.state.ark = ark

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if settings.proxy_api_key and not request.url.path.startswith(
            ("/health", "/media/reference/")
        ):
            authorization = request.headers.get("authorization", "")
            if authorization != f"Bearer {settings.proxy_api_key}":
                return openai_error("Invalid API key", 401, "invalid_api_key")
        try:
            return await call_next(request)
        except ModelArkError as exc:
            return openai_error(str(exc), exc.status_code, "modelark_error")
        except TranslationError as exc:
            return openai_error(str(exc), 400, "invalid_request")
        except UploadTooLarge as exc:
            return openai_error(str(exc), 413, "upload_too_large")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/media/reference/{name}", include_in_schema=False)
    async def reference_media(name: str):
        path = media.resolve(name)
        if not path:
            raise HTTPException(status_code=404, detail="Reference not found")
        media_type = "video/quicktime" if path.suffix == ".mov" else None
        return FileResponse(path, media_type=media_type)

    async def create_video(request: Request) -> VideoObject:
        data, upload = await parse_create_request(request)
        hosted_reference: tuple[str, str] | None = None
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
            )
        media.cleanup()
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

    async def get_video(video_id: str) -> VideoObject:
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

    async def video_content(video_id: str):
        task = await ark.get_task(video_id)
        if task.get("status") != "succeeded":
            return openai_error(
                f"Video is not ready (status: {task.get('status')})",
                409,
                "video_not_ready",
            )
        url = (task.get("content") or {}).get("video_url")
        if not isinstance(url, str):
            raise HTTPException(
                status_code=502, detail="Successful ModelArk task has no video_url"
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

        return StreamingResponse(stream(), media_type="video/mp4")

    app.add_api_route("/v1/videos/{video_id}/content", video_content, methods=["GET"])
    app.add_api_route(
        "/videos/{video_id}/content",
        video_content,
        methods=["GET"],
        include_in_schema=False,
    )

    return app
