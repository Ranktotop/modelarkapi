"""Seedance native fields, response fields, list and delete (T22, research §13)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.models import capabilities_for

V25 = "dreamina-seedance-2-5-260628"
V20 = "dreamina-seedance-2-0-260128"
V10 = "seedance-1-0-pro-250528"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "proxy-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
    )


class FakeArk:
    def __init__(self, task: dict[str, Any] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.created: list[dict[str, Any]] = []
        self.task = task or {"id": "cgt-1", "model": V25, "status": "queued"}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            self.created.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "cgt-1"})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        if request.url.path.endswith("/tasks"):
            return httpx.Response(200, json={"items": [], "total": 0})
        return httpx.Response(200, json=self.task)


async def call(settings: Settings, fake: FakeArk, method: str, path: str, **kwargs):
    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        return await client.request(method, path, **kwargs)


@pytest.mark.parametrize(
    "body",
    [
        {"model": V10, "prompt": "fox", "ratio": "adaptive"},
        {"model": V25, "prompt": "fox", "camera_fixed": True},
        {
            "model": V10,
            "prompt": "fox",
            "camera_fixed": True,
            "reference_urls": [
                {"url": "https://i.example.com/a.png", "media_type": "image"},
                {"url": "https://i.example.com/b.png", "media_type": "image"},
            ],
        },
        {"model": V25, "prompt": "fox", "priority": 10},
        {"model": V10, "prompt": "fox", "priority": 3},
        {"model": V25, "prompt": "fox", "service_tier": "flex"},
        {"model": V10, "prompt": "fox", "service_tier": "turbo"},
        {"model": V25, "prompt": "fox", "execution_expires_after": 60},
        {"model": V10, "prompt": "fox", "frames": 30},
        {"model": V10, "prompt": "fox", "frames": 293},
    ],
)
async def test_native_fields_are_checked(settings: Settings, body: dict[str, Any]):
    fake = FakeArk()

    response = await call(settings, fake, "POST", "/v1/videos", json=body)

    assert response.status_code == 400, response.text
    assert not fake.created


@pytest.mark.parametrize(
    "body",
    [
        {"model": V10, "prompt": "fox", "camera_fixed": True, "frames": 29},
        {"model": V10, "prompt": "fox", "service_tier": "flex"},
        {
            "model": V10,
            "prompt": "fox",
            "ratio": "adaptive",
            "input_reference_url": "https://i.example.com/a.png",
            "input_reference_media_type": "image",
            "input_reference_role": "first_frame",
        },
        {"model": V20, "prompt": "fox", "priority": 9, "execution_expires_after": 3600},
    ],
)
async def test_valid_native_fields_pass(settings: Settings, body: dict[str, Any]):
    fake = FakeArk()

    response = await call(settings, fake, "POST", "/v1/videos", json=body)

    assert response.status_code == 200, response.text


async def test_long_safety_identifiers_are_hashed(settings: Settings):
    fake = FakeArk()
    user = "user-" + "x" * 80

    response = await call(
        settings,
        fake,
        "POST",
        "/v1/videos",
        json={"model": V25, "prompt": "f", "user": user},
    )

    assert response.status_code == 200
    assert (
        fake.created[0]["safety_identifier"]
        == hashlib.sha256(user.encode()).hexdigest()
    )


async def test_response_carries_the_task_settings(settings: Settings):
    fake = FakeArk(
        {
            "id": "cgt-1",
            "model": V25,
            "status": "succeeded",
            "seed": 42,
            "resolution": "1080p",
            "ratio": "16:9",
            "duration": 5,
            "framespersecond": 24,
            "output_format": "mov",
            "generate_audio": True,
            "draft_task_id": "cgt-draft",
            "content": {"video_url": "https://x.example.com/v.mov"},
        }
    )

    response = await call(settings, fake, "GET", "/v1/videos/cgt-1")

    body = response.json()
    assert body["seed"] == 42
    assert body["resolution"] == "1080p"
    assert body["ratio"] == "16:9"
    assert body["framespersecond"] == 24
    assert body["output_format"] == "mov"
    assert body["generate_audio"] is True
    assert body["draft_task_id"] == "cgt-draft"


async def test_list_accepts_service_tier_and_limits_pages(settings: Settings):
    fake = FakeArk()

    listed = await call(
        settings, fake, "GET", "/v1/videos?filter.service_tier=flex&page_num=2"
    )
    too_far = await call(settings, fake, "GET", "/v1/videos?page_num=501")

    assert listed.status_code == 200
    assert fake.requests[0].url.params["filter.service_tier"] == "flex"
    assert too_far.status_code == 400


@pytest.mark.parametrize(
    ("upstream", "status"),
    [("queued", "cancelled"), ("succeeded", "succeeded")],
)
async def test_delete_reports_what_happened(
    settings: Settings, upstream: str, status: str
):
    fake = FakeArk({"id": "cgt-1", "model": V25, "status": upstream})

    response = await call(settings, fake, "DELETE", "/v1/videos/cgt-1")

    assert response.status_code == 200
    assert response.json()["provider_status"] == status
    assert response.json()["object"] == "video.deleted"
    assert response.json()["deleted"] is True


async def test_running_task_cannot_be_deleted(settings: Settings):
    fake = FakeArk({"id": "cgt-1", "model": V25, "status": "running"})

    response = await call(settings, fake, "DELETE", "/v1/videos/cgt-1")

    assert response.status_code == 409
    assert not any(r.method == "DELETE" for r in fake.requests)


def test_capabilities_follow_the_research():
    v25 = capabilities_for(V25)
    v10 = capabilities_for(V10)
    v15 = capabilities_for("seedance-1-5-pro-251215")

    assert v25["parameters"]["seconds"]["default"] == "auto"
    assert v25["tasks"]["edit"]["references"][0]["min_seconds"] == 4
    assert "camera_fixed" in v10["native_fields"]
    assert "camera_fixed" not in v25["native_fields"]
    assert "generate_audio" not in v10["parameters"]
    assert v15["deprecation"] == {
        "shutdown_at": "2026-11-11T09:00:00Z",
        "replacement": "dreamina-seedance-2-0-mini",
    }


@pytest.mark.parametrize(
    ("model", "resolution", "ratio", "size"),
    [
        (V25, "480p", "16:9", "854x480"),
        (V25, "480p", "9:16", "480x854"),
        (V20, "480p", "16:9", "864x496"),
        (V10, "720p", "16:9", "1248x704"),
        (V10, "1080p", "9:16", "1088x1920"),
        (V25, "720p", "16:9", "1280x720"),
    ],
)
def test_size_follows_the_model_family(model, resolution, ratio, size):
    from modelark_proxy.translation import byteplus_to_openai

    video = byteplus_to_openai(
        {
            "id": "cgt-1",
            "model": model,
            "status": "running",
            "resolution": resolution,
            "ratio": ratio,
        }
    )

    assert video.size == size
