from __future__ import annotations

import asyncio
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
                "content": {
                    "video_url": "https://out.volces.com/generated.mp4",
                    "last_frame_url": "https://out.volces.com/last.png",
                },
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


@pytest.mark.asyncio
async def test_first_and_last_frame_roles_and_user_are_translated(settings: Settings):
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
                "prompt": "Transition between the frames",
                "user": "hashed-user-42",
                "reference_assets": [
                    {"id": "asset-first", "type": "image", "role": "first_frame"},
                    {"id": "asset-last", "type": "image", "role": "last_frame"},
                ],
            },
        )
    assert response.status_code == 200
    upstream = json.loads(captured[0].content)
    assert [item["role"] for item in upstream["content"][1:]] == [
        "first_frame",
        "last_frame",
    ]
    assert upstream["safety_identifier"] == "hashed-user-42"


@pytest.mark.asyncio
async def test_list_videos_is_translated(settings: Settings):
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        task = {
            "id": "cgt-list-1",
            "model": "dreamina-seedance-2-0-260128",
            "status": "running",
            "created_at": 100,
            "updated_at": 110,
        }
        return httpx.Response(200, json={"items": [task], "total": 3})

    app = create_app(settings, ark_transport=httpx.MockTransport(handler))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get(
            "/v1/videos?limit=2&page_num=1&filter.status=running&ignored=x"
        )
    assert response.status_code == 200
    assert response.json()["data"][0]["status"] == "in_progress"
    assert response.json()["has_more"] is True
    assert dict(captured[0].url.params) == {
        "page_size": "2",
        "page_num": "1",
        "filter.status": "running",
    }


@pytest.mark.asyncio
async def test_last_frame_is_streamed(settings: Settings):
    download = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"png-bytes")
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
        response = await client.get("/v1/videos/cgt-123/last_frame")
    assert response.status_code == 200
    assert response.content == b"png-bytes"
    assert response.headers["content-type"].startswith("image/png")


@pytest.mark.asyncio
async def test_multiple_reference_media_are_uploaded_and_deleted(settings: Settings):
    app = create_app(settings, ark_transport=ark_transport([]))
    fake_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 32
    fake_mp3 = b"ID3" + b"x" * 32
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/media/references",
            files=[
                ("files", ("clip.mp4", fake_mp4, "video/mp4")),
                ("files", ("sound.mp3", fake_mp3, "audio/mpeg")),
            ],
        )
        assert response.status_code == 200
        references = response.json()["data"]
        assert [item["kind"] for item in references] == ["video", "audio"]
        assert all(item["url"].startswith(settings.public_base_url) for item in references)

        media_response = await client.get(
            f"/media/reference/{references[1]['id']}"
        )
        assert media_response.content == fake_mp3
        assert media_response.headers["content-type"].startswith("audio/mpeg")

        deleted = await client.delete(
            f"/v1/media/references/{references[0]['id']}"
        )
        assert deleted.json()["deleted"] is True


@pytest.mark.asyncio
async def test_previous_task_last_frame_can_continue_a_video(settings: Settings):
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
                "prompt": "Continue seamlessly",
                "input_reference_task_id": "cgt-previous",
            },
        )
    assert response.status_code == 200
    assert captured[0].method == "GET"
    upstream = json.loads(captured[1].content)
    assert upstream["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://out.volces.com/last.png"},
        "role": "first_frame",
    }


@pytest.mark.asyncio
async def test_many_video_tasks_are_submitted_concurrently(settings: Settings):
    active = 0
    max_active = 0
    counter = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active, counter
        assert request.method == "POST"
        counter += 1
        task_number = counter
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return httpx.Response(200, json={"id": f"cgt-parallel-{task_number}"})

    app = create_app(settings, ark_transport=httpx.MockTransport(handler))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        requests = [
            asyncio.create_task(
                client.post(
                    "/v1/videos",
                    json={"prompt": f"Parallel scene {index}", "duration": 4},
                )
            )
            for index in range(32)
        ]
        await asyncio.sleep(0.01)
        health = await client.get("/health")
        responses = await asyncio.gather(*requests)

    assert health.status_code == 200
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 32
    assert max_active >= 16
