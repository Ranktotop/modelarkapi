from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
from server import UISettings, _SuccessfulHealthCheckFilter, create_app


def _access_record(path: str, status_code: int) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", "GET", path, "1.1", status_code),
        None,
    )


def test_access_log_filter_hides_only_successful_health_checks():
    access_filter = _SuccessfulHealthCheckFilter()

    assert access_filter.filter(_access_record("/health", 200)) is False
    assert access_filter.filter(_access_record("/health?full=true", 204)) is False
    assert access_filter.filter(_access_record("/health", 500)) is True
    assert access_filter.filter(_access_record("/api/session", 200)) is True


@pytest.fixture
def ui_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UISettings:
    monkeypatch.setenv("UI_AUTH_DISABLED", "true")
    settings = UISettings()
    settings.proxy_url = "https://proxy.example/v1"
    settings.proxy_key = "proxy-test"
    settings.password = ""
    settings.auth_disabled = True
    settings.session_secret = ""
    settings.cookie_secure = False
    settings.db_path = tmp_path / "ui.db"
    settings.poll_interval_seconds = 3600
    settings.cleanup_interval_seconds = 3600
    settings.job_ttl_seconds = 86_400
    return settings


def proxy_transport(captured: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        path = request.url.path
        if request.method == "GET" and path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {
                            "id": "dreamina-seedance-2-0-260128",
                            "object": "model",
                            "name": "Seedance 2.0",
                            "capabilities": {
                                "resolutions": ["480p", "720p", "1080p", "4k"],
                                "ratios": ["adaptive", "16:9"],
                                "durations": [-1, 4, 5],
                                "defaults": {
                                    "resolution": "720p",
                                    "ratio": "adaptive",
                                    "duration": 5,
                                },
                            },
                        },
                        {
                            "id": "dreamina-seedance-2-0-fast-260128",
                            "object": "model",
                            "name": "Seedance 2.0 Fast",
                            "capabilities": {
                                "resolutions": ["480p", "720p"],
                                "ratios": ["adaptive", "16:9"],
                                "durations": [-1, 4, 5],
                                "defaults": {
                                    "resolution": "720p",
                                    "ratio": "adaptive",
                                    "duration": 5,
                                },
                            },
                        },
                    ],
                },
            )
        if request.method == "POST" and path.endswith("/videos"):
            return httpx.Response(
                200,
                json={
                    "id": "cgt-ui-1",
                    "status": "queued",
                    "created_at": 100,
                    "model": "seedance",
                },
            )
        if request.method == "GET" and path.endswith("/videos/cgt-ui-1"):
            return httpx.Response(
                200,
                json={
                    "id": "cgt-ui-1",
                    "status": "completed",
                    "created_at": 100,
                    "last_frame_available": True,
                },
            )
        if request.method == "GET" and path.endswith("/content"):
            return httpx.Response(
                200, content=b"video-data", headers={"content-type": "video/mp4"}
            )
        if request.method == "DELETE":
            return httpx.Response(200, json={"id": "cgt-ui-1", "status": "failed"})
        return httpx.Response(404, json={"error": "not_found"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_ui_config_exposes_proxy_model_options(ui_settings: UISettings):
    app = create_app(
        ui_settings,
        proxy_transport=proxy_transport([]),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        response = await client.get("/api/config")

    assert response.status_code == 200
    config = response.json()
    assert [model["label"] for model in config["models"]] == [
        "Seedance 2.0",
        "Seedance 2.0 Fast",
    ]
    assert config["models"][0]["capabilities"]["resolutions"] == [
        "480p",
        "720p",
        "1080p",
        "4k",
    ]


@pytest.mark.asyncio
async def test_ui_config_preserves_proxy_credential_error(ui_settings: UISettings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": {
                    "message": "ModelArk credentials are currently invalid: "
                    "ARK_API_KEY was rejected with HTTP 401",
                    "code": "upstream_credentials_invalid",
                }
            },
        )

    app = create_app(
        ui_settings,
        proxy_transport=httpx.MockTransport(handler),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        response = await client.get("/api/config")

    assert response.status_code == 503
    assert "ARK_API_KEY" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ui_creates_tracks_and_streams_job(ui_settings: UISettings):
    captured: list[httpx.Request] = []
    app = create_app(
        ui_settings,
        proxy_transport=proxy_transport(captured),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        created = await client.post(
            "/api/videos",
            headers={"X-UI-Request": "1"},
            json={
                "model": "seedance",
                "ui_mode": "text",
                "prompt": "A small test scene",
                "duration": 4,
            },
        )
        assert created.status_code == 200
        assert created.json()["provider"]["status"] == "queued"

        status = await client.get("/api/videos/cgt-ui-1")
        assert status.json()["provider"]["status"] == "completed"

        jobs = await client.get("/api/videos")
        assert jobs.json()["data"][0]["prompt"] == "A small test scene"

        content = await client.get("/api/videos/cgt-ui-1/content")
        assert content.content == b"video-data"
        assert content.headers["content-type"].startswith("video/mp4")

    assert captured[0].headers["authorization"] == "Bearer proxy-test"


@pytest.mark.asyncio
async def test_ui_keeps_ui_only_fields_out_of_the_proxy_request(
    ui_settings: UISettings,
):
    captured: list[httpx.Request] = []
    app = create_app(
        ui_settings,
        proxy_transport=proxy_transport(captured),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        await client.post(
            "/api/videos",
            headers={"X-UI-Request": "1"},
            json={
                "model": "seedance",
                "ui_mode": "multimodal",
                "ui_references": [{"filename": "clip.mp4", "kind": "video"}],
                "prompt": "A small test scene",
            },
        )
        jobs = await client.get("/api/videos")

    upstream = json.loads(captured[0].content)
    assert "ui_mode" not in upstream
    assert "ui_references" not in upstream
    assert upstream["prompt"] == "A small test scene"

    stored = jobs.json()["data"][0]["request"]
    assert stored["ui_mode"] == "multimodal"
    assert stored["ui_references"] == [{"filename": "clip.mp4", "kind": "video"}]


@pytest.mark.asyncio
async def test_ui_rejects_unauthenticated_api_calls(
    ui_settings: UISettings, tmp_path: Path
):
    ui_settings.password = "correct horse battery staple"
    ui_settings.username = "studio-owner"
    ui_settings.auth_disabled = False
    ui_settings.session_secret = "x" * 32
    ui_settings.db_path = tmp_path / "authenticated.db"
    app = create_app(
        ui_settings,
        proxy_transport=proxy_transport([]),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        denied = await client.get("/api/videos")
        assert denied.status_code == 401

        bad_login = await client.post(
            "/api/login", json={"username": "studio-owner", "password": "wrong"}
        )
        assert bad_login.status_code == 401

        login = await client.post(
            "/api/login",
            json={
                "username": "studio-owner",
                "password": "correct horse battery staple",
            },
        )
        assert login.status_code == 200
        assert "httponly" in login.headers["set-cookie"].lower()

        allowed = await client.get("/api/videos")
        assert allowed.status_code == 200
        assert allowed.headers["x-frame-options"] == "DENY"
        assert allowed.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_ui_rate_limits_failed_logins(ui_settings: UISettings, tmp_path: Path):
    ui_settings.username = "studio-owner"
    ui_settings.password = "correct horse battery staple"
    ui_settings.auth_disabled = False
    ui_settings.session_secret = "x" * 32
    ui_settings.login_max_attempts = 3
    ui_settings.login_window_seconds = 900
    ui_settings.db_path = tmp_path / "rate-limited.db"
    app = create_app(
        ui_settings,
        proxy_transport=proxy_transport([]),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        for _ in range(3):
            denied = await client.post(
                "/api/login", json={"username": "studio-owner", "password": "wrong"}
            )
            assert denied.status_code == 401
        limited = await client.post(
            "/api/login",
            json={
                "username": "studio-owner",
                "password": "correct horse battery staple",
            },
        )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_ui_accepts_many_parallel_job_submissions(ui_settings: UISettings):
    active = 0
    max_active = 0
    counter = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active, counter
        if request.method != "POST":
            return httpx.Response(404, json={"error": "not_found"})
        counter += 1
        task_number = counter
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return httpx.Response(
            200,
            json={
                "id": f"cgt-ui-parallel-{task_number}",
                "status": "queued",
                "created_at": 100 + task_number,
            },
        )

    app = create_app(
        ui_settings,
        proxy_transport=httpx.MockTransport(handler),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        responses = await asyncio.gather(
            *(
                client.post(
                    "/api/videos",
                    headers={"X-UI-Request": "1"},
                    json={
                        "model": "seedance",
                        "ui_mode": "text",
                        "prompt": f"Parallel UI scene {index}",
                        "duration": 4,
                    },
                )
                for index in range(24)
            )
        )
        jobs = await client.get("/api/videos")

    assert all(response.status_code == 200 for response in responses)
    assert len(jobs.json()["data"]) == 24
    assert max_active >= 12


@pytest.mark.asyncio
async def test_background_status_polling_is_bounded_and_parallel(
    ui_settings: UISettings,
):
    active_status = 0
    max_active_status = 0
    counter = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_status, max_active_status, counter
        if request.method == "POST":
            counter += 1
            return httpx.Response(
                200,
                json={
                    "id": f"cgt-poll-{counter}",
                    "status": "queued",
                    "created_at": 100 + counter,
                },
            )
        if request.method == "GET":
            active_status += 1
            max_active_status = max(max_active_status, active_status)
            await asyncio.sleep(0.04)
            active_status -= 1
            return httpx.Response(
                200,
                json={
                    "id": request.url.path.rsplit("/", 1)[-1],
                    "status": "completed",
                    "created_at": 100,
                },
            )
        return httpx.Response(200, json={"status": "failed"})

    ui_settings.poll_interval_seconds = 1
    ui_settings.poll_concurrency = 8
    app = create_app(
        ui_settings,
        proxy_transport=httpx.MockTransport(handler),
        static_dir=Path("/does-not-exist"),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://studio"
        ) as client,
    ):
        await asyncio.gather(
            *(
                client.post(
                    "/api/videos",
                    headers={"X-UI-Request": "1"},
                    json={
                        "model": "seedance",
                        "ui_mode": "text",
                        "prompt": f"Polling scene {index}",
                    },
                )
                for index in range(18)
            )
        )
        await asyncio.sleep(1.2)
        jobs = (await client.get("/api/videos")).json()["data"]

    assert max_active_status == 8
    assert all(job["provider"]["status"] == "completed" for job in jobs)
