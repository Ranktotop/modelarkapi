from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile

TERMINAL_STATUSES = {"completed", "failed"}


class UISettings:
    def __init__(self) -> None:
        self.proxy_url = os.getenv(
            "MODELARK_PROXY_URL", "http://modelark-video-proxy:8080/v1"
        ).rstrip("/")
        self.proxy_key = os.getenv(
            "MODELARK_PROXY_API_KEY", os.getenv("PROXY_API_KEY", "")
        )
        self.password = os.getenv("UI_PASSWORD", "")
        self.auth_disabled = os.getenv("UI_AUTH_DISABLED", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.session_secret = os.getenv("UI_SESSION_SECRET", "")
        self.cookie_secure = os.getenv("UI_COOKIE_SECURE", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.job_ttl_seconds = int(os.getenv("UI_JOB_TTL_SECONDS", "86400"))
        self.cleanup_interval_seconds = int(
            os.getenv("UI_CLEANUP_INTERVAL_SECONDS", "900")
        )
        self.poll_interval_seconds = int(os.getenv("UI_POLL_INTERVAL_SECONDS", "10"))
        self.poll_concurrency = int(os.getenv("UI_POLL_CONCURRENCY", "20"))
        self.max_proxy_connections = int(os.getenv("UI_MAX_PROXY_CONNECTIONS", "100"))
        self.session_ttl_seconds = int(os.getenv("UI_SESSION_TTL_SECONDS", "43200"))
        self.db_path = Path(os.getenv("UI_DB_PATH", "./data/ui/ui.db"))
        self.model_name = os.getenv("UI_MODEL_NAME", "seedance")

        if not self.password and not self.auth_disabled:
            raise RuntimeError(
                "UI_PASSWORD is required unless UI_AUTH_DISABLED=true is explicitly set"
            )
        if self.password and len(self.session_secret) < 32:
            raise RuntimeError(
                "UI_SESSION_SECRET must contain at least 32 characters when UI_PASSWORD is set"
            )


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.lock, self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    terminal_at INTEGER,
                    expires_at INTEGER
                )
                """
            )

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        result["provider"] = json.loads(result.pop("response_json"))
        return result

    def add(self, task: dict[str, Any], request_data: dict[str, Any]) -> dict[str, Any]:
        now = int(time.time())
        task_id = str(task["id"])
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO jobs
                    (id, status, prompt, model, mode, request_json, response_json,
                     created_at, updated_at, terminal_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    task_id,
                    str(task.get("status", "queued")),
                    str(request_data.get("prompt", "")),
                    str(request_data.get("model", "")),
                    str(request_data.get("ui_mode", "text")),
                    json.dumps(request_data, separators=(",", ":")),
                    json.dumps(task, separators=(",", ":")),
                    int(task.get("created_at") or now),
                    now,
                ),
            )
        return self.get(task_id) or {}

    def update(self, task_id: str, task: dict[str, Any], ttl: int) -> None:
        now = int(time.time())
        status = str(task.get("status", "queued"))
        terminal_at = now if status in TERMINAL_STATUSES else None
        with self.lock, self.connection:
            current = self.connection.execute(
                "SELECT terminal_at FROM jobs WHERE id = ?", (task_id,)
            ).fetchone()
            if not current:
                return
            terminal_at = current["terminal_at"] or terminal_at
            expires_at = terminal_at + ttl if terminal_at else None
            self.connection.execute(
                """
                UPDATE jobs SET status = ?, response_json = ?, updated_at = ?,
                    terminal_at = ?, expires_at = ? WHERE id = ?
                """,
                (
                    status,
                    json.dumps(task, separators=(",", ":")),
                    now,
                    terminal_at,
                    expires_at,
                    task_id,
                ),
            )

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (task_id,)
            ).fetchone()
        return self._serialize(row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._serialize(row) for row in rows]

    def active_ids(self) -> list[str]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT id FROM jobs WHERE terminal_at IS NULL"
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def expired_ids(self, now: int) -> list[str]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT id FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def delete(self, task_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM jobs WHERE id = ?", (task_id,))

    def close(self) -> None:
        with self.lock:
            self.connection.close()


def _session_token(settings: UISettings) -> str:
    expires = int(time.time()) + settings.session_ttl_seconds
    nonce = secrets.token_urlsafe(12)
    payload = f"{expires}.{nonce}"
    signature = hmac.new(
        settings.session_secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{payload}.{encoded}"


def _valid_session(token: str | None, settings: UISettings) -> bool:
    if not settings.password:
        return True
    if not token:
        return False
    try:
        expires_text, nonce, supplied = token.split(".", 2)
        if int(expires_text) <= int(time.time()):
            return False
        payload = f"{expires_text}.{nonce}"
        signature = hmac.new(
            settings.session_secret.encode(), payload.encode(), hashlib.sha256
        ).digest()
        expected = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return hmac.compare_digest(supplied, expected)
    except (TypeError, ValueError):
        return False


def create_app(
    settings: UISettings | None = None,
    *,
    proxy_transport: httpx.AsyncBaseTransport | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    settings = settings or UISettings()
    store = JobStore(settings.db_path)
    headers = {"Authorization": f"Bearer {settings.proxy_key}"}
    proxy = httpx.AsyncClient(
        base_url=settings.proxy_url,
        headers=headers,
        timeout=60,
        limits=httpx.Limits(
            max_connections=settings.max_proxy_connections,
            max_keepalive_connections=min(settings.max_proxy_connections, 20),
        ),
        transport=proxy_transport,
    )

    async def proxy_json(
        method: str, path: str, **kwargs: Any
    ) -> tuple[int, dict[str, Any]]:
        response = await proxy.request(method, path, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {"error": {"message": response.text or "Proxy returned no JSON"}}
        return response.status_code, body

    async def refresh_jobs() -> None:
        semaphore = asyncio.Semaphore(settings.poll_concurrency)

        async def refresh_one(task_id: str) -> None:
            try:
                async with semaphore:
                    status, body = await proxy_json(
                        "GET", f"/videos/{quote(task_id, safe='')}"
                    )
                    if status < 400:
                        store.update(task_id, body, settings.job_ttl_seconds)
            except httpx.HTTPError:
                pass

        await asyncio.gather(*(refresh_one(task_id) for task_id in store.active_ids()))

    async def cleanup_jobs() -> None:
        async def delete_one(task_id: str) -> None:
            with suppress(httpx.HTTPError):
                await proxy_json("DELETE", f"/videos/{quote(task_id, safe='')}")
            store.delete(task_id)

        await asyncio.gather(
            *(delete_one(task_id) for task_id in store.expired_ids(int(time.time())))
        )

    async def maintenance_loop() -> None:
        poll_elapsed = settings.poll_interval_seconds
        while True:
            if poll_elapsed >= settings.poll_interval_seconds:
                await refresh_jobs()
                poll_elapsed = 0
            await cleanup_jobs()
            sleep_for = min(
                settings.poll_interval_seconds, settings.cleanup_interval_seconds
            )
            await asyncio.sleep(sleep_for)
            poll_elapsed += sleep_for

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await refresh_jobs()
        await cleanup_jobs()
        task = asyncio.create_task(maintenance_loop())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await proxy.aclose()
            store.close()

    app = FastAPI(title="Seedance Studio UI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.proxy = proxy

    @app.exception_handler(httpx.HTTPError)
    async def upstream_unavailable(_: Request, exc: httpx.HTTPError) -> JSONResponse:
        return JSONResponse(
            {"error": {"message": f"ModelArk proxy is unavailable: {exc}"}},
            status_code=502,
        )

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        path = request.url.path
        public_api = path in {"/api/login", "/api/session", "/health"}
        if path.startswith("/api/") and not public_api:
            if not _valid_session(request.cookies.get("seedance_session"), settings):
                return JSONResponse(
                    {"error": "authentication_required"}, status_code=401
                )
            if request.method not in {"GET", "HEAD", "OPTIONS"} and (
                request.headers.get("x-ui-request") != "1"
            ):
                return JSONResponse({"error": "csrf_check_failed"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/session")
    async def session(request: Request) -> dict[str, bool]:
        return {
            "authenticated": _valid_session(
                request.cookies.get("seedance_session"), settings
            ),
            "required": bool(settings.password),
        }

    @app.post("/api/login")
    async def login(request: Request) -> JSONResponse:
        data = await request.json()
        supplied = str(data.get("password", "")) if isinstance(data, dict) else ""
        if settings.password and not hmac.compare_digest(supplied, settings.password):
            return JSONResponse({"error": "invalid_password"}, status_code=401)
        response = JSONResponse({"authenticated": True})
        if settings.password:
            response.set_cookie(
                "seedance_session",
                _session_token(settings),
                max_age=settings.session_ttl_seconds,
                httponly=True,
                secure=settings.cookie_secure,
                samesite="strict",
                path="/",
            )
        return response

    @app.delete("/api/session")
    async def logout() -> JSONResponse:
        response = JSONResponse({"authenticated": False})
        response.delete_cookie("seedance_session", path="/")
        return response

    @app.get("/api/config")
    async def config() -> dict[str, Any]:
        return {
            "model": settings.model_name,
            "job_ttl_seconds": settings.job_ttl_seconds,
            "resolutions": ["480p", "720p"],
            "ratios": ["adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            "durations": list(range(4, 16)),
            "reference_limits": {"image": 9, "video": 3, "audio": 3},
        }

    @app.post("/api/references")
    async def upload_references(request: Request) -> JSONResponse:
        form = await request.form()
        uploads = [
            value for _, value in form.multi_items() if isinstance(value, UploadFile)
        ]
        if not uploads:
            raise HTTPException(status_code=400, detail="No files supplied")
        files = []
        for upload in uploads:
            upload.file.seek(0)
            files.append(
                (
                    "files",
                    (
                        upload.filename or "reference",
                        upload.file,
                        upload.content_type or "application/octet-stream",
                    ),
                )
            )
        status, body = await proxy_json(
            "POST", "/media/references", files=files, timeout=600
        )
        return JSONResponse(body, status_code=status)

    @app.delete("/api/references/{reference_id}")
    async def delete_reference(reference_id: str) -> JSONResponse:
        status, body = await proxy_json(
            "DELETE", f"/media/references/{quote(reference_id, safe='')}"
        )
        return JSONResponse(body, status_code=status)

    @app.post("/api/videos")
    async def create_video(request: Request) -> JSONResponse:
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="JSON object required")
        upstream = {key: value for key, value in data.items() if key != "ui_mode"}
        status, body = await proxy_json("POST", "/videos", json=upstream)
        if status < 400:
            body = store.add(body, data)
        return JSONResponse(body, status_code=status)

    @app.get("/api/videos")
    async def list_videos() -> dict[str, Any]:
        return {"object": "list", "data": store.list()}

    @app.get("/api/videos/{task_id}")
    async def get_video(task_id: str) -> JSONResponse:
        status, body = await proxy_json("GET", f"/videos/{quote(task_id, safe='')}")
        if status < 400:
            store.update(task_id, body, settings.job_ttl_seconds)
            body = store.get(task_id) or body
        return JSONResponse(body, status_code=status)

    @app.delete("/api/videos/{task_id}")
    async def delete_video(task_id: str) -> JSONResponse:
        status, body = await proxy_json("DELETE", f"/videos/{quote(task_id, safe='')}")
        if status < 400 or status == 404:
            store.delete(task_id)
        return JSONResponse(body, status_code=status)

    async def stream_proxy_file(
        task_id: str, suffix: str, filename: str
    ) -> StreamingResponse | JSONResponse:
        url = f"/videos/{quote(task_id, safe='')}/{suffix}"
        request = proxy.build_request("GET", url)
        response = await proxy.send(request, stream=True)
        if response.is_error:
            content = await response.aread()
            await response.aclose()
            try:
                body = json.loads(content)
            except ValueError:
                body = {"error": "download_failed"}
            return JSONResponse(body, status_code=response.status_code)

        async def stream() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        headers = {"Content-Disposition": f'inline; filename="{filename}"'}
        return StreamingResponse(
            stream(),
            media_type=response.headers.get("content-type"),
            headers=headers,
        )

    @app.get("/api/videos/{task_id}/content")
    async def video_content(task_id: str):
        return await stream_proxy_file(task_id, "content", f"{task_id}.mp4")

    @app.get("/api/videos/{task_id}/last-frame")
    async def last_frame(task_id: str):
        return await stream_proxy_file(task_id, "last_frame", f"{task_id}.png")

    resolved_static = static_dir or Path(__file__).resolve().parent / "static"
    if resolved_static.is_dir():
        app.mount("/", StaticFiles(directory=resolved_static, html=True), name="studio")

    return app
