from __future__ import annotations

import asyncio
import hmac
import json
import logging
import mimetypes
import time
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .asset_jobs import AssetJobManager
from .assets import AssetAPIError, AssetClient
from .client import ModelArkClient, ModelArkError
from .config import Settings
from .errors import openai_error
from .media import MediaStore, UploadTooLarge, upload_chunks
from .providers import DEFAULT_PROVIDER, ProviderRegistry, ProviderUnavailable
from .providers import seedance
from .providers.seedance import SeedanceProvider
from .schemas import MediaReference, MediaReferenceList, VideoList, VideoObject
from .translation import TranslationError

logger = logging.getLogger(__name__)
# Seedance 2.5 accepts 30 images + 10 videos + 10 audio clips in one request.
MAX_REFERENCE_UPLOADS = 50
REFERENCE_SIZE_LIMITS = {
    "image": 30 * 1024 * 1024,
    "video": 200 * 1024 * 1024,
    "audio": 15 * 1024 * 1024,
}


def modelark_error_code(error: ModelArkError) -> str:
    body = error.body if isinstance(error.body, dict) else {}
    upstream_error = body.get("error", body)
    code = upstream_error.get("code") if isinstance(upstream_error, dict) else None
    return str(code) if code else "modelark_error"


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
        lambda data, references: seedance.build_task_payload(
            data, settings, None, internal_asset_references=references
        ),
        media.remove,
    )
    providers = ProviderRegistry(
        [SeedanceProvider(settings, ark, asset_jobs, media, download_transport)]
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
            # Each validator returns (message, unreachable). "unreachable" marks a
            # network-level failure, which says nothing about the credential and
            # must not lock the proxy out of its own upstream.
            async def validate_ark_api_key() -> tuple[str | None, bool]:
                if not settings.ark_api_key:
                    return "ARK_API_KEY is not configured", False
                try:
                    async with asyncio.timeout(
                        settings.credential_validation_timeout_seconds
                    ):
                        await ark.validate_api_key()
                except ModelArkError as exc:
                    return (
                        f"ARK_API_KEY was rejected with HTTP {exc.status_code}",
                        False,
                    )
                except TimeoutError:
                    return "ARK_API_KEY validation timed out", True
                except httpx.HTTPError:
                    return "ARK_API_KEY validation could not reach ModelArk", True
                except Exception:
                    logger.exception("Unexpected ARK_API_KEY validation failure")
                    return "ARK_API_KEY validation failed unexpectedly", False
                return None, False

            async def validate_iam_credentials() -> tuple[str | None, bool]:
                if not settings.byteplus_access_key_id:
                    return "BYTEPLUS_ACCESS_KEY_ID is not configured", False
                if not settings.byteplus_secret_access_key:
                    return "BYTEPLUS_SECRET_ACCESS_KEY is not configured", False
                try:
                    async with asyncio.timeout(
                        settings.credential_validation_timeout_seconds
                    ):
                        await assets.validate_management_access()
                except AssetAPIError:
                    return (
                        (
                            "BYTEPLUS_ACCESS_KEY_ID/BYTEPLUS_SECRET_ACCESS_KEY "
                            "were rejected by the ModelArk management API"
                        ),
                        False,
                    )
                except TimeoutError:
                    return "IAM credential validation timed out", True
                except httpx.HTTPError:
                    return (
                        (
                            "IAM credential validation could not reach the "
                            "ModelArk management API"
                        ),
                        True,
                    )
                except Exception:
                    logger.exception("Unexpected IAM credential validation failure")
                    return "IAM credential validation failed unexpectedly", False
                return None, False

            ark_result, iam_result = await asyncio.gather(
                validate_ark_api_key(), validate_iam_credentials()
            )
            results = (("ark_api_key", ark_result), ("iam", iam_result))
            fields: dict[str, str] = {}
            for field, (message, unreachable) in results:
                if message is None:
                    fields[field] = "valid"
                elif unreachable:
                    # Keep a credential that already worked; otherwise stay
                    # undecided so the fast recheck loop can settle it.
                    fields[field] = (
                        "valid" if credential_state[field] == "valid" else "checking"
                    )
                else:
                    fields[field] = "invalid"
            if "invalid" in fields.values():
                status = "invalid"
            elif "checking" in fields.values():
                status = "checking"
            else:
                status = "valid"
            errors = [message for _, (message, _) in results if message]
            credential_state.update(
                status=status,
                message="; ".join(errors) if errors else None,
                last_checked_at=datetime.now(UTC).isoformat(),
                **fields,
            )
            if errors:
                logger.warning(
                    "ModelArk credential check reported %s: %s",
                    status,
                    "; ".join(errors),
                )

        async def maintain_credential_state() -> None:
            while True:
                interval = settings.credential_validation_interval_seconds
                if credential_state["status"] != "valid":
                    interval = min(
                        interval, settings.credential_revalidation_interval_seconds
                    )
                await asyncio.sleep(interval)
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
    app.state.providers = providers

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
            if credential_state["status"] == "checking":
                return openai_error(
                    f"ModelArk credentials could not be validated yet: {message}",
                    503,
                    "upstream_credentials_unavailable",
                )
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
        except ProviderUnavailable as exc:
            return openai_error(str(exc), 404, "model_unavailable")
        except UploadTooLarge as exc:
            return openai_error(str(exc), 413, "upload_too_large")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": settings.app_version,
            "credentials": deepcopy(credential_state),
        }

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
        if len(uploads) > MAX_REFERENCE_UPLOADS:
            raise TranslationError(
                f"At most {MAX_REFERENCE_UPLOADS} reference files are allowed "
                "per upload"
            )

        saved: list[str] = []
        references: list[MediaReference] = []
        try:
            for upload in uploads:
                name, media_type = await media.save(
                    upload_chunks(upload),
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
        model = data.get("model")
        if not isinstance(model, str) or not model.strip():
            raise TranslationError("model is required")
        return await providers.for_model(model).create_video(data, upload)

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
        return await providers.providers[DEFAULT_PROVIDER].list_videos(request)

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
        return await providers.for_video(video_id).get_video(video_id)

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
        return await providers.for_video(video_id).delete_video(video_id)

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
        return await providers.for_video(video_id).stream_output(
            video_id, field, media_type
        )

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
