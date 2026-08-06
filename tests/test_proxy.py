from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        public_base_url="https://seedance-proxy.example.com",
        media_dir=tmp_path / "media",
    )


def ark_transport(captured: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-123"})
        return httpx.Response(
            200,
            json={
                "id": "cgt-123",
                "model": "dreamina-seedance-2-0-260128",
                "status": "succeeded",
                "content": {"video_url": "https://out.volces.com/generated.mp4"},
                "created_at": 100,
                "updated_at": 200,
                "resolution": "720p",
                "ratio": "16:9",
                "duration": 5,
                "usage": {"total_tokens": 1000, "completion_tokens": 1000},
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_text_to_video_translation(settings: Settings):
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            json={
                "model": "openai/dreamina-seedance-2-0-260128",
                "prompt": "A fox runs through snow",
                "seconds": "5",
                "size": "1280x720",
            },
        )
    assert response.status_code == 200
    assert response.json()["id"] == "cgt-123"
    upstream = json.loads(captured[0].content)
    assert upstream == {
        "model": "dreamina-seedance-2-0-260128",
        "content": [{"type": "text", "text": "A fox runs through snow"}],
        "duration": 5,
        "generate_audio": True,
        "resolution": "720p",
        "ratio": "16:9",
    }
    assert captured[0].headers["authorization"] == "Bearer ark-test"


@pytest.mark.asyncio
async def test_uploaded_video_is_sniffed_and_hosted(settings: Settings):
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    fake_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 32
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            data={"model": "seedance", "prompt": "Extend this shot", "seconds": "6"},
            # LiteLLM currently labels non-image input_reference bytes as image/png.
            files={"input_reference": ("input_reference.png", fake_mp4, "image/png")},
        )
    assert response.status_code == 200
    upstream = json.loads(captured[0].content)
    reference = upstream["content"][1]
    assert reference["type"] == "video_url"
    assert reference["role"] == "reference_video"
    assert reference["video_url"]["url"].startswith(
        "https://seedance-proxy.example.com/media/reference/"
    )
    assert list(settings.media_dir.glob("*.mp4"))


@pytest.mark.asyncio
async def test_status_translation(settings: Settings):
    app = create_app(settings, ark_transport=ark_transport([]))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/v1/videos/cgt-123")
    body = response.json()
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["size"] == "1280x720"
    assert body["seconds"] == "5"
    assert body["usage"]["total_tokens"] == 1000


@pytest.mark.asyncio
async def test_download_is_streamed(settings: Settings):
    download = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"video-bytes")
    )
    app = create_app(
        settings, ark_transport=ark_transport([]), download_transport=download
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/v1/videos/cgt-123/content")
    assert response.status_code == 200
    assert response.content == b"video-bytes"
    assert response.headers["content-type"].startswith("video/mp4")


@pytest.mark.asyncio
async def test_upload_requires_public_base_url(settings: Settings):
    settings.public_base_url = None
    app = create_app(settings, ark_transport=ark_transport([]))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            data={"prompt": "test"},
            files={"input_reference": ("clip.mp4", b"1234ftypmp42", "video/mp4")},
        )
    assert response.status_code == 400
    assert "PUBLIC_BASE_URL" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_authorized_asset_is_translated_without_public_url(settings: Settings):
    settings.public_base_url = None
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            json={
                "model": "seedance",
                "prompt": "The person in Image 1 walks into the studio.",
                "asset_id": "asset-20260807-portrait",
            },
        )
    assert response.status_code == 200
    upstream = json.loads(captured[0].content)
    assert upstream["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "asset://asset-20260807-portrait"},
        "role": "reference_image",
    }


@pytest.mark.asyncio
async def test_typed_authorized_assets_are_translated(settings: Settings):
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            json={
                "prompt": "Use Image 1, Video 1, and Audio 1.",
                "reference_assets": [
                    {"id": "asset-image", "type": "image"},
                    {"id": "asset://asset-video", "type": "video"},
                    {"id": "asset-audio", "type": "audio"},
                ],
            },
        )
    assert response.status_code == 200
    upstream = json.loads(captured[0].content)
    assert [item["type"] for item in upstream["content"]] == [
        "text",
        "image_url",
        "video_url",
        "audio_url",
    ]
    assert upstream["content"][2]["video_url"]["url"] == "asset://asset-video"


@pytest.mark.asyncio
async def test_invalid_asset_id_is_rejected_before_modelark(settings: Settings):
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            json={"prompt": "test", "asset_id": "https://attacker.example/file"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert captured == []
