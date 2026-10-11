"""Per-provider credential state, health, and request gating (T5)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.schemas import VideoObject


def base_settings(tmp_path: Path, **values: Any) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        credential_revalidation_interval_seconds=3600,
        **values,
    )


def modelark_settings(tmp_path: Path, **values: Any) -> Settings:
    return base_settings(
        tmp_path,
        ark_api_key="ark-test",
        byteplus_access_key_id="ak-test",
        byteplus_secret_access_key="sk-test",
        **values,
    )


def ark(status: int) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(status, json={"items": [], "total": 0})
    )


def management_ok() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"Result": {"Items": [], "TotalCount": 0}}
        )
    )


def kling(status: int, code: int = 0) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/account/costs"
        assert request.headers["authorization"] == "Bearer kling-key"
        return httpx.Response(status, json={"code": code, "message": "x", "data": {}})

    return httpx.MockTransport(handler)


class StubKling:
    """Stands in for the Kling provider until T14 implements it."""

    name = "kling"

    def owns_video(self, video_id: str) -> bool:
        return video_id.startswith("vid-kling-")

    async def create_video(self, data, upload) -> VideoObject:
        return VideoObject(id="vid-kling-1", status="queued", model=data["model"])


async def run(app, *calls):
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        return [await call(client) for call in calls]


async def test_health_reports_each_provider(tmp_path: Path):
    app = create_app(
        modelark_settings(tmp_path, kling_api_key="kling-key"),
        ark_transport=ark(200),
        asset_transport=management_ok(),
        kling_transport=kling(200),
    )

    (health,) = await run(app, lambda c: c.get("/health"))

    providers = health.json()["providers"]
    assert providers["modelark"]["status"] == "valid"
    assert providers["kling"]["status"] == "valid"
    assert providers["google"]["status"] == "disabled"
    assert health.json()["credentials"]["status"] == "valid"


async def test_invalid_modelark_does_not_block_other_providers(tmp_path: Path):
    app = create_app(
        modelark_settings(tmp_path, kling_api_key="kling-key"),
        ark_transport=ark(401),
        asset_transport=management_ok(),
        kling_transport=kling(200),
    )
    app.state.providers.providers["kling"] = StubKling()

    kling_video, seedance_video = await run(
        app,
        lambda c: c.post("/v1/videos", json={"model": "kling-3.0", "prompt": "fox"}),
        lambda c: c.post(
            "/v1/videos",
            json={"model": "dreamina-seedance-2-5-260628", "prompt": "fox"},
        ),
    )

    assert kling_video.status_code == 200
    assert seedance_video.status_code == 503
    assert seedance_video.json()["error"]["code"] == "upstream_credentials_invalid"
    assert "ModelArk" in seedance_video.json()["error"]["message"]


async def test_invalid_kling_blocks_only_kling(tmp_path: Path):
    app = create_app(
        modelark_settings(tmp_path, kling_api_key="kling-key"),
        ark_transport=ark(200),
        asset_transport=management_ok(),
        kling_transport=kling(401, code=1002),
    )
    app.state.providers.providers["kling"] = StubKling()

    health, kling_video = await run(
        app,
        lambda c: c.get("/health"),
        lambda c: c.post("/v1/videos", json={"model": "kling-3.0", "prompt": "fox"}),
    )

    assert health.json()["providers"]["kling"]["status"] == "invalid"
    assert "KLING_API_KEY" in health.json()["providers"]["kling"]["message"]
    assert health.json()["providers"]["modelark"]["status"] == "valid"
    assert kling_video.status_code == 503
    assert kling_video.json()["error"]["code"] == "upstream_credentials_invalid"


async def test_proxy_starts_without_modelark(tmp_path: Path):
    app = create_app(
        base_settings(tmp_path, kling_api_key="kling-key"),
        kling_transport=kling(200),
    )

    health, models, seedance_video = await run(
        app,
        lambda c: c.get("/health"),
        lambda c: c.get("/v1/models"),
        lambda c: c.post(
            "/v1/videos",
            json={"model": "dreamina-seedance-2-5-260628", "prompt": "fox"},
        ),
    )

    assert health.json()["providers"]["modelark"]["status"] == "disabled"
    assert models.status_code == 200
    assert models.json()["data"] == []
    assert seedance_video.status_code == 404
    assert seedance_video.json()["error"]["code"] == "model_unavailable"


async def test_proxy_starts_without_any_provider(tmp_path: Path, caplog):
    app = create_app(base_settings(tmp_path))

    with caplog.at_level(logging.WARNING):
        (health,) = await run(app, lambda c: c.get("/health"))

    assert {p["status"] for p in health.json()["providers"].values()} == {"disabled"}
    assert "No video provider is configured" in caplog.text


async def test_google_checks_gemini_key_and_vertex_access(tmp_path: Path):
    seen: list[str] = []

    def google(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host + request.url.path)
        if request.url.host == "generativelanguage.googleapis.com":
            assert request.headers["x-goog-api-key"] == "gemini-key"
            return httpx.Response(200, json={"models": []})
        assert request.headers["authorization"] == "Bearer vertex-token"
        return httpx.Response(403, json={"error": {"message": "denied"}})

    async def token() -> str:
        return "vertex-token"

    app = create_app(
        base_settings(tmp_path, gemini_api_key="gemini-key", vertex_project="proj-1"),
        google_transport=httpx.MockTransport(google),
        vertex_token_source=token,
    )

    (health,) = await run(app, lambda c: c.get("/health"))

    google_state = health.json()["providers"]["google"]
    assert google_state["status"] == "invalid"
    assert google_state["gemini"] == "valid"
    assert google_state["vertex"] == "invalid"
    assert "VERTEX_PROJECT" in google_state["message"]
    assert (
        "aiplatform.googleapis.com/v1beta1/projects/proj-1/locations/global/interactions"
        in seen
    )


async def test_proxy_key_is_still_required_for_every_provider(tmp_path: Path):
    settings = modelark_settings(tmp_path, kling_api_key="kling-key")
    settings.proxy_api_key = "p" * 40
    app = create_app(
        settings,
        ark_transport=ark(200),
        asset_transport=management_ok(),
        kling_transport=kling(200),
        validate_startup_credentials=False,
    )
    app.state.providers.providers["kling"] = StubKling()

    responses = await run(
        app,
        lambda c: c.post("/v1/videos", json={"model": "kling-3.0", "prompt": "fox"}),
        lambda c: c.post(
            "/v1/videos",
            json={"model": "dreamina-seedance-2-5-260628", "prompt": "fox"},
        ),
        lambda c: c.post("/v1/videos", json={"model": "veo-3.1-generate-001"}),
    )

    assert [response.status_code for response in responses] == [401, 401, 401]
