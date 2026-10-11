from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.models import spec_for
from modelark_proxy.providers import provider_name_for


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("dreamina-seedance-2-5-260628", "modelark"),
        ("openai/dreamina-seedance-2-0-fast-260128", "modelark"),
        ("seedance-1-0-pro-250528", "modelark"),
        ("veo-3.1-generate-001", "google"),
        ("veo-3.1-fast-generate-preview", "google"),
        ("google/veo-3.1-lite-generate-001", "google"),
        ("gemini-omni-1.1-flash", "google"),
        ("gemini-omni-1.1-flash-preview", "google"),
        ("kling-3.0-omni", "kling"),
        ("kling-v2-5-turbo", "kling"),
        ("kling/kling-lip-sync", "kling"),
        ("openai/kling-3.0", "kling"),
    ],
)
def test_models_route_to_their_provider(model: str, provider: str):
    assert provider_name_for(model) == provider


def test_seedance_specs_belong_to_modelark():
    assert spec_for("dreamina-seedance-2-5-260628").provider == "modelark"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://seedance-proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "proxy-jobs.db",
    )


async def test_unconfigured_provider_is_rejected_without_calling_modelark(
    settings: Settings,
):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"id": "cgt-unexpected"})

    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(handler),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos", json={"model": "veo-3.1-generate-001", "prompt": "fox"}
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_unavailable"
    assert calls == []
