from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import mimetypes
import time
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from starlette.datastructures import UploadFile as StarletteUploadFile

from .asset_jobs import AssetJobManager
from .assets import AssetAPIError, AssetClient
from .client import ModelArkClient, ModelArkError
from .config import Settings
from .credentials import (
    CredentialMonitor,
    ProviderCredentialsError,
    google_check,
    kling_check,
    modelark_check,
)
from .errors import openai_error
from .google_auth import TokenSource, VertexTokenSource
from .ids import decode_video_id, encode_video_id
from .litellm_export import export_model_list
from .media import MediaStore, UploadTooLarge, upload_chunks
from .outputs import OutputStore
from .prompt_guides import PromptGuides
from .provider_jobs import ProviderJobStore, purge_expired
from .providers import (
    DEFAULT_PROVIDER,
    ProviderRegistry,
    ProviderUnavailable,
    VideoProvider,
    strip_model_namespace,
)
from .providers import seedance
from .providers.seedance import SeedanceProvider
from .schemas import MediaReference, MediaReferenceList, VideoList, VideoObject
from .translation import TranslationError
from .webhooks import WebhookDispatcher, validate_webhook_url
from .workers import JobRunner

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


INTEGER_FIELDS = {
    "duration",
    "frames",
    "seed",
    "execution_expires_after",
    "priority",
    "n",
}
BOOLEAN_FIELDS = {
    "generate_audio",
    "watermark",
    "camera_fixed",
    "return_last_frame",
    "real_human",
    "enhance_prompt",
}
# Object or array fields; clients may send each as a JSON string, which is the
# one encoding every LiteLLM version forwards unchanged.
STRUCTURED_FIELDS = {
    "reference_urls",
    "content",
    "references",
    "shots",
    "provider_options",
    "speech",
    "audio",
    "commerce",
    "selections",
    "metadata",
    "extra_body",
    "video",
}
_BRACKETS = re.compile(r"\[([^\[\]]*)\]")


def _coerce(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if key in INTEGER_FIELDS:
        try:
            return int(value)
        except ValueError:
            return value
    if key in BOOLEAN_FIELDS:
        return value.lower() in {"1", "true", "yes", "on"}
    return value


def _set_path(container: Any, tokens: list[str], key: str, value: Any) -> Any:
    """Apply one `name[a][]`-style form field the way LiteLLM serializes it.

    An empty token appends to an array; within an array of objects a new object
    starts as soon as a key repeats.
    """
    if not tokens:
        return _coerce(key, value)
    token, rest = tokens[0], tokens[1:]
    if token == "":
        items = container if isinstance(container, list) else []
        if not rest:
            items.append(value)
            return items
        last = items[-1] if items else None
        if not isinstance(last, dict) or (len(rest) == 1 and rest[0] in last):
            last = {}
            items.append(last)
        _set_path(last, rest, key, value)
        return items
    mapping = container if isinstance(container, dict) else {}
    mapping[token] = _set_path(mapping.get(token), rest, token, value)
    return mapping


def normalize_fields(data: dict[str, Any]) -> dict[str, Any]:
    for key in STRUCTURED_FIELDS.intersection(data):
        value = data[key]
        if isinstance(value, str) and value.strip()[:1] in {"[", "{"}:
            try:
                data[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    extra = data.pop("extra_body", None)
    if isinstance(extra, dict):
        for key, value in extra.items():
            data.setdefault(key, value)
        normalize_fields(data)
    return data


def form_to_data(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Rebuild a request body from multipart fields (plain or bracket notation)."""
    data: dict[str, Any] = {}
    for name, value in items:
        bracket = name.find("[")
        if bracket <= 0:
            data[name] = _coerce(name, value)
            continue
        base = name[:bracket]
        tokens = _BRACKETS.findall(name[bracket:])
        data[base] = _set_path(data.get(base), tokens, base, value)
    return normalize_fields(data)


async def parse_create_request(
    request: Request,
) -> tuple[dict[str, Any], UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        fields: list[tuple[str, Any]] = []
        upload: UploadFile | None = None
        for key, value in form.multi_items():
            if key == "input_reference" and isinstance(value, StarletteUploadFile):
                upload = value
                continue
            if isinstance(value, StarletteUploadFile):
                continue
            fields.append((key, value))
        return form_to_data(fields), upload
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
    return normalize_fields(body), None


def with_public_id(video: VideoObject, model: str | None = None) -> VideoObject:
    """Expose the LiteLLM-routable ID; see ids.py for why."""
    video.id = encode_video_id(video.id, model or video.model)
    return video


def create_app(
    settings: Settings | None = None,
    *,
    ark_transport: httpx.AsyncBaseTransport | None = None,
    asset_transport: httpx.AsyncBaseTransport | None = None,
    download_transport: httpx.AsyncBaseTransport | None = None,
    webhook_transport: httpx.AsyncBaseTransport | None = None,
    google_transport: httpx.AsyncBaseTransport | None = None,
    kling_transport: httpx.AsyncBaseTransport | None = None,
    vertex_token_source: TokenSource | None = None,
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
    check_timeout = httpx.Timeout(settings.credential_validation_timeout_seconds)
    google_http = httpx.AsyncClient(timeout=check_timeout, transport=google_transport)
    kling_http = httpx.AsyncClient(timeout=check_timeout, transport=kling_transport)
    if vertex_token_source is None and settings.vertex_project:
        vertex_token_source = VertexTokenSource(
            Path(settings.google_application_credentials)
            if settings.google_application_credentials
            else None
        )
    credentials = CredentialMonitor(
        {
            "modelark": modelark_check(settings, ark, assets)
            if settings.modelark_configured
            else None,
            "google": google_check(settings, google_http, vertex_token_source)
            if settings.google_configured
            else None,
            "kling": kling_check(settings, kling_http)
            if settings.kling_configured
            else None,
        },
        validate=validate_startup_credentials,
    )
    # Kept for /health's legacy `credentials` field (ModelArk only).
    credential_state = credentials.state["modelark"]
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
        if settings.modelark_configured
        else []
    )
    provider_jobs = ProviderJobStore(
        settings.provider_job_db, settings.provider_job_ttl_seconds
    )
    outputs = OutputStore(settings.output_dir)
    prompt_guides = PromptGuides(settings.prompt_guides_dir)
    webhooks = WebhookDispatcher(
        settings.provider_job_db,
        settings.webhook_secret,
        transport=webhook_transport,
        timeout_seconds=settings.webhook_timeout_seconds,
        max_attempts=settings.webhook_max_attempts,
    )
    job_runner = JobRunner(
        provider_jobs,
        settings.provider_worker_concurrency,
        poll_interval_seconds=settings.provider_poll_interval_seconds,
        retry_base_seconds=settings.asset_transient_retry_seconds,
        retry_max_seconds=settings.asset_transient_retry_max_seconds,
    )

    def video_provider(video_id: str) -> VideoProvider:
        provider = providers.for_video(video_id)
        credentials.require(provider.name)
        return provider

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async def cleanup_media() -> None:
            while True:
                await asyncio.sleep(settings.media_cleanup_interval_seconds)
                media.cleanup()
                purge_expired(provider_jobs, outputs)

        async def get_public_video(video_id: str) -> VideoObject:
            video = await video_provider(video_id).get_video(video_id)
            return with_public_id(video)

        async def deliver_webhooks() -> None:
            while True:
                await asyncio.sleep(settings.webhook_interval_seconds)
                try:
                    await webhooks.check(get_public_video)
                    await webhooks.deliver_due()
                except Exception:
                    logger.exception("Webhook maintenance failed")

        async def maintain_asset_jobs() -> None:
            while True:
                if credential_state["status"] == "valid":
                    await asset_jobs.maintenance()
                await asyncio.sleep(settings.asset_maintenance_interval_seconds)

        async def maintain_credential_state() -> None:
            while True:
                interval = settings.credential_validation_interval_seconds
                if credentials.needs_recheck():
                    interval = min(
                        interval, settings.credential_revalidation_interval_seconds
                    )
                await asyncio.sleep(interval)
                await credentials.refresh()

        cleanup_task: asyncio.Task[None] | None = None
        webhook_task: asyncio.Task[None] | None = None
        asset_task: asyncio.Task[None] | None = None
        credential_task: asyncio.Task[None] | None = None
        try:
            if not any(map(credentials.enabled, ("modelark", "google", "kling"))):
                logger.warning(
                    "No video provider is configured; set ARK_API_KEY, "
                    "GEMINI_API_KEY/VERTEX_PROJECT, or KLING_API_KEY"
                )
            if validate_startup_credentials:
                await credentials.refresh()
            media.cleanup()
            purge_expired(provider_jobs, outputs)
            job_runner.resume()
            cleanup_task = asyncio.create_task(cleanup_media())
            webhook_task = asyncio.create_task(deliver_webhooks())
            asset_task = asyncio.create_task(maintain_asset_jobs())
            if validate_startup_credentials:
                credential_task = asyncio.create_task(maintain_credential_state())
            yield
        finally:
            if cleanup_task is not None:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
            if webhook_task is not None:
                webhook_task.cancel()
                with suppress(asyncio.CancelledError):
                    await webhook_task
            await webhooks.close()
            if asset_task is not None:
                asset_task.cancel()
                with suppress(asyncio.CancelledError):
                    await asset_task
            if credential_task is not None:
                credential_task.cancel()
                with suppress(asyncio.CancelledError):
                    await credential_task
            await job_runner.close()
            provider_jobs.close()
            await asset_jobs.close()
            await assets.close()
            await ark.close()
            await google_http.aclose()
            await kling_http.aclose()

    app = FastAPI(
        title="ModelArk OpenAI Video Proxy", version="0.2.0", lifespan=lifespan
    )
    app.state.settings = settings
    app.state.ark = ark
    app.state.assets = assets
    app.state.asset_jobs = asset_jobs
    app.state.credential_state = credential_state
    app.state.credentials = credentials
    app.state.providers = providers
    app.state.provider_jobs = provider_jobs
    app.state.outputs = outputs
    app.state.job_runner = job_runner
    app.state.webhooks = webhooks

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
        except ProviderCredentialsError as exc:
            return openai_error(str(exc), 503, exc.code)
        except UploadTooLarge as exc:
            return openai_error(str(exc), 413, "upload_too_large")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": settings.app_version,
            "credentials": deepcopy(credential_state),
            "providers": credentials.snapshot(),
        }

    async def collect_models() -> list[dict[str, Any]]:
        nonlocal model_cache, model_cache_expires_at
        if not credentials.enabled("modelark"):
            return []
        credentials.require("modelark")
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
        models = []
        for model in model_cache:
            guide = prompt_guides.for_model(model["id"])
            models.append(
                {
                    "id": model["id"],
                    "object": "model",
                    "owned_by": "modelark",
                    "name": model["label"],
                    "capabilities": model["capabilities"],
                    "links": {
                        "prompt_guide": guide.summary()["url"] if guide else None
                    },
                }
            )
        return models

    @app.get("/v1/models")
    @app.get("/models", include_in_schema=False)
    async def list_models() -> dict[str, Any]:
        return {"object": "list", "data": await collect_models()}

    @app.get("/v1/models/{model_id:path}")
    @app.get("/models/{model_id:path}", include_in_schema=False)
    async def get_model(model_id: str) -> dict[str, Any]:
        bare = strip_model_namespace(model_id)
        model = next((m for m in await collect_models() if m["id"] == bare), None)
        if model is None:
            raise ProviderUnavailable(f"Model '{bare}' is not available on this proxy")
        guide = prompt_guides.for_model(bare)
        return {
            **model,
            "prompt_guide": {**guide.summary(), "markdown": guide.markdown()}
            if guide
            else None,
        }

    @app.get("/v1/prompt-guides")
    @app.get("/prompt-guides", include_in_schema=False)
    async def list_prompt_guides() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [guide.summary() for guide in prompt_guides.all()],
        }

    @app.get("/v1/prompt-guides/{guide_id}")
    @app.get("/prompt-guides/{guide_id}", include_in_schema=False)
    async def get_prompt_guide(guide_id: str, request: Request):
        guide = prompt_guides.get(guide_id)
        if guide is None:
            return openai_error(
                f"Prompt guide '{guide_id}' not found", 404, "not_found"
            )
        if "application/json" in request.headers.get("accept", ""):
            return {**guide.summary(), "markdown": guide.markdown()}
        return PlainTextResponse(
            guide.markdown(), media_type="text/markdown; charset=utf-8"
        )

    @app.get("/v1/litellm/config")
    async def litellm_config(
        format: str = "yaml",
        api_base: str | None = None,
        name_template: str = "{family_slug}_api",
    ):
        base = api_base or (
            f"{settings.public_base_url.rstrip('/')}/v1"
            if settings.public_base_url
            else "http://modelarkapi_server:8080/v1"
        )
        try:
            config = export_model_list(
                await collect_models(),
                prompt_guides,
                api_base=base,
                public_base_url=settings.public_base_url,
                name_template=name_template,
            )
        except (KeyError, IndexError) as exc:
            raise TranslationError(
                "name_template may only use {family_slug} and {model}"
            ) from exc
        if format == "json":
            return config
        return PlainTextResponse(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True, width=1000),
            media_type="application/yaml",
        )

    @app.get("/v1/real-human/configuration")
    @app.get("/real-human/configuration", include_in_schema=False)
    async def real_human_configuration() -> dict[str, Any]:
        if credentials.enabled("modelark"):
            credentials.require("modelark")
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
        source_id = data.get("input_reference_task_id")
        if isinstance(source_id, str):
            data["input_reference_task_id"] = decode_video_id(source_id)
        webhook_url = data.pop("webhook_url", None)
        if webhook_url is not None:
            if not settings.webhook_secret:
                raise TranslationError(
                    "webhook_url requires WEBHOOK_SECRET to be configured on the proxy"
                )
            try:
                validate_webhook_url(str(webhook_url))
            except ValueError as exc:
                raise TranslationError(str(exc)) from exc
        provider = providers.for_model(model)
        credentials.require(provider.name)
        video = await provider.create_video(data, upload)
        if webhook_url is not None:
            webhooks.watch(video.id, str(webhook_url), video.status)
        return with_public_id(video, strip_model_namespace(model))

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
        if not credentials.enabled(DEFAULT_PROVIDER):
            return VideoList(data=[])
        credentials.require(DEFAULT_PROVIDER)
        videos = await providers.providers[DEFAULT_PROVIDER].list_videos(request)
        videos.data = [with_public_id(video) for video in videos.data]
        return videos

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
        video_id = decode_video_id(video_id)
        return with_public_id(await video_provider(video_id).get_video(video_id))

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
        video_id = decode_video_id(video_id)
        video = await video_provider(video_id).delete_video(video_id)
        return with_public_id(video)

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
        video_id = decode_video_id(video_id)
        return await video_provider(video_id).stream_output(video_id, field, media_type)

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
