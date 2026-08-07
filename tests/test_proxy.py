from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from modelark_proxy.app import create_app as create_proxy_app
from modelark_proxy.config import Settings


def create_app(*args, **kwargs):
    """Keep endpoint tests focused; startup validation has dedicated tests."""
    kwargs.setdefault("validate_startup_credentials", False)
    return create_proxy_app(*args, **kwargs)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://seedance-proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "proxy-jobs.db",
        byteplus_access_key_id="ak-test",
        byteplus_secret_access_key="sk-test",
        byteplus_asset_group_id="",
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
async def test_models_are_discovered_from_available_activations(settings: Settings):
    settings.byteplus_access_key_id = "ak-test"
    settings.byteplus_secret_access_key = "sk-test"
    management_requests: list[httpx.Request] = []

    def management_handler(request: httpx.Request) -> httpx.Response:
        management_requests.append(request)
        action = request.url.params["Action"]
        if action == "ListModelActivations":
            return httpx.Response(
                200,
                json={
                    "Result": {
                        "Items": [
                            {
                                "FoundationModelName": "dreamina-seedance-2-0-fast",
                                "DisplayName": "Dreamina-Seedance-2.0-fast",
                                "State": "Available",
                            },
                            {
                                "FoundationModelName": "dreamina-seedance-2-0",
                                "DisplayName": "Dreamina-Seedance-2.0",
                                "State": "Unavailable",
                            },
                            {
                                "FoundationModelName": "seed-2-0-pro",
                                "DisplayName": "Dola-Seed-2.0-pro",
                                "State": "Available",
                            },
                        ]
                    }
                },
            )
        assert action == "ListFoundationModelVersions"
        return httpx.Response(
            200,
            json={
                "Result": {
                    "Items": [
                        {
                            "FoundationModelName": "dreamina-seedance-2-0-fast",
                            "ModelVersion": "260128",
                            "Status": "Published",
                        }
                    ]
                }
            },
        )

    app = create_app(
        settings,
        ark_transport=ark_transport([]),
        asset_transport=httpx.MockTransport(management_handler),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/v1/models")
        cached = await client.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "dreamina-seedance-2-0-fast-260128",
                "object": "model",
                "owned_by": "modelark",
                "name": "Seedance 2.0 Fast",
                "capabilities": {
                    "resolutions": ["480p", "720p"],
                    "ratios": [
                        "adaptive",
                        "16:9",
                        "9:16",
                        "1:1",
                        "4:3",
                        "3:4",
                        "21:9",
                    ],
                    "durations": [-1, *range(4, 16)],
                    "defaults": {
                        "resolution": "720p",
                        "ratio": "adaptive",
                        "duration": 5,
                    },
                },
            },
        ],
    }
    assert cached.json() == response.json()
    assert len(management_requests) == 2


def test_settings_allow_missing_upstream_credentials(tmp_path: Path):
    configured = Settings(
        _env_file=None,
        ark_api_key="",
        byteplus_access_key_id="",
        byteplus_secret_access_key="",
        media_dir=tmp_path / "media",
    )
    assert configured.ark_api_key == ""
    assert not configured.model_management_configured


@pytest.mark.asyncio
async def test_startup_validates_ark_and_iam_credentials(settings: Settings):
    ark_requests: list[httpx.Request] = []
    management_requests: list[httpx.Request] = []

    def ark_handler(request: httpx.Request) -> httpx.Response:
        ark_requests.append(request)
        return httpx.Response(200, json={"items": [], "total": 0})

    def management_handler(request: httpx.Request) -> httpx.Response:
        management_requests.append(request)
        return httpx.Response(
            200, json={"Result": {"Items": [], "TotalCount": 0}}
        )

    app = create_proxy_app(
        settings,
        ark_transport=httpx.MockTransport(ark_handler),
        asset_transport=httpx.MockTransport(management_handler),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        health = await client.get("/health")

    assert health.json()["credentials"]["status"] == "valid"
    assert len(ark_requests) == 1
    assert ark_requests[0].method == "GET"
    assert ark_requests[0].url.path.endswith("/contents/generations/tasks")
    assert ark_requests[0].url.params["page_size"] == "1"
    assert len(management_requests) == 1
    assert management_requests[0].url.params["Action"] == "ListModelActivations"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_credential", ["ark", "iam"])
async def test_invalid_upstream_credentials_keep_proxy_alive_but_block_routes(
    settings: Settings, invalid_credential: str
):
    def ark_handler(request: httpx.Request) -> httpx.Response:
        if invalid_credential == "ark":
            return httpx.Response(401, json={"error": {"message": "invalid key"}})
        return httpx.Response(200, json={"items": [], "total": 0})

    def management_handler(request: httpx.Request) -> httpx.Response:
        if invalid_credential == "iam":
            return httpx.Response(
                403,
                json={
                    "ResponseMetadata": {
                        "Error": {"Message": "invalid access key"}
                    }
                },
            )
        return httpx.Response(
            200, json={"Result": {"Items": [], "TotalCount": 0}}
        )

    app = create_proxy_app(
        settings,
        ark_transport=httpx.MockTransport(ark_handler),
        asset_transport=httpx.MockTransport(management_handler),
    )
    expected = "ARK_API_KEY" if invalid_credential == "ark" else "BYTEPLUS"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        health = await client.get("/health")
        blocked = await client.get("/v1/models")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["credentials"]["status"] == "invalid"
    assert expected in health.json()["credentials"]["message"]
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "upstream_credentials_invalid"
    assert expected in blocked.json()["error"]["message"]


@pytest.mark.asyncio
async def test_credentials_are_rechecked_and_routes_recover(settings: Settings):
    settings.credential_validation_interval_seconds = 0.01
    ark_checks = 0

    def ark_handler(request: httpx.Request) -> httpx.Response:
        nonlocal ark_checks
        ark_checks += 1
        if ark_checks == 1:
            return httpx.Response(401, json={"error": {"message": "invalid key"}})
        return httpx.Response(200, json={"items": [], "total": 0})

    def management_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"Result": {"Items": [], "TotalCount": 0}}
        )

    app = create_proxy_app(
        settings,
        ark_transport=httpx.MockTransport(ark_handler),
        asset_transport=httpx.MockTransport(management_handler),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        blocked = await client.get("/v1/real-human/configuration")
        for _ in range(50):
            health = await client.get("/health")
            if health.json()["credentials"]["status"] == "valid":
                break
            await asyncio.sleep(0.01)
        recovered = await client.get("/v1/real-human/configuration")

    assert blocked.status_code == 503
    assert health.json()["credentials"]["status"] == "valid"
    assert recovered.status_code == 200
    assert ark_checks >= 2


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
async def test_modelark_billing_error_code_is_preserved(settings: Settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": "ResourcePackageExhausted",
                    "message": "The applicable resource package is exhausted",
                }
            },
        )

    app = create_app(settings, ark_transport=httpx.MockTransport(handler))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos", json={"model": "seedance-test", "prompt": "test"}
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ResourcePackageExhausted"
    assert "resource package is exhausted" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_video_creation_requires_model(settings: Settings):
    captured: list[httpx.Request] = []
    app = create_app(settings, ark_transport=ark_transport(captured))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post("/v1/videos", json={"prompt": "test"})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "model is required"
    assert captured == []


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
            data={"model": "seedance-test", "prompt": "test"},
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
                "model": "seedance-test",
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
            json={
                "model": "seedance-test",
                "prompt": "test",
                "asset_id": "https://attacker.example/file",
            },
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert captured == []


@pytest.mark.asyncio
async def test_proxy_api_key_protects_rest_routes(settings: Settings):
    settings.proxy_api_key = "p" * 32
    app = create_app(settings, ark_transport=ark_transport([]))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        health = await client.get("/health")
        denied = await client.post(
            "/v1/videos", json={"model": "seedance-test", "prompt": "test"}
        )
        allowed = await client.post(
            "/v1/videos",
            headers={"Authorization": f"Bearer {settings.proxy_api_key}"},
            json={"model": "seedance-test", "prompt": "test"},
        )
    assert health.status_code == 200
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"
    assert allowed.status_code == 200


def test_protected_mode_requires_long_proxy_key(tmp_path: Path):
    with pytest.raises(ValueError, match="PROXY_API_KEY"):
        Settings(
            _env_file=None,
            ark_api_key="ark-test",
            byteplus_access_key_id="ak-test",
            byteplus_secret_access_key="sk-test",
            require_proxy_api_key=True,
            proxy_api_key=None,
            media_dir=tmp_path / "media",
        )
    with pytest.raises(ValueError, match="32 characters"):
        Settings(
            _env_file=None,
            ark_api_key="ark-test",
            byteplus_access_key_id="ak-test",
            byteplus_secret_access_key="sk-test",
            require_proxy_api_key=True,
            proxy_api_key="too-short",
            media_dir=tmp_path / "media",
        )


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
                "model": "seedance-test",
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
        assert all(
            item["url"].startswith(settings.public_base_url) for item in references
        )

        media_response = await client.get(f"/media/reference/{references[1]['id']}")
        assert media_response.content == fake_mp3
        assert media_response.headers["content-type"].startswith("audio/mpeg")
        assert media_response.headers["cache-control"] == "private, no-store, max-age=0"
        assert media_response.headers["x-content-type-options"] == "nosniff"

        deleted = await client.delete(f"/v1/media/references/{references[0]['id']}")
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
                "model": "seedance-test",
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
                    json={
                        "model": "seedance-test",
                        "prompt": f"Parallel scene {index}",
                        "duration": 4,
                    },
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


@pytest.mark.asyncio
async def test_real_human_reference_is_registered_used_and_deleted(settings: Settings):
    settings.byteplus_access_key_id = "ak-test"
    settings.byteplus_secret_access_key = "sk-test"
    settings.byteplus_asset_group_id = "group-person"
    settings.asset_job_db = settings.media_dir.parent / "asset-jobs.db"
    settings.asset_maintenance_interval_seconds = 0.01
    asset_requests: list[httpx.Request] = []

    def assets_handler(request: httpx.Request) -> httpx.Response:
        asset_requests.append(request)
        action = request.url.params["Action"]
        if action == "CreateAsset":
            return httpx.Response(200, json={"Result": {"Id": "asset-temporary"}})
        if action == "GetAsset":
            return httpx.Response(
                200, json={"Result": {"Id": "asset-temporary", "Status": "Active"}}
            )
        if action == "DeleteAsset":
            return httpx.Response(200, json={"Result": {}})
        if action == "ListAssets":
            return httpx.Response(200, json={"Result": {"Items": [], "TotalCount": 0}})
        raise AssertionError(action)

    ark_requests: list[httpx.Request] = []

    def ark_handler(request: httpx.Request) -> httpx.Response:
        ark_requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-real-human"})
        return httpx.Response(
            200,
            json={
                "id": "cgt-real-human",
                "status": "succeeded",
                "model": "seedance-test",
                "created_at": 100,
                "updated_at": 200,
                "content": {"video_url": "https://out.volces.com/generated.mp4"},
            },
        )

    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(ark_handler),
        asset_transport=httpx.MockTransport(assets_handler),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        upload = await client.post(
            "/v1/media/references",
            files={"files": ("portrait.mp4", b"1234ftypmp42", "video/mp4")},
        )
        reference = upload.json()["data"][0]
        created = await client.post(
            "/v1/videos",
            json={
                "model": "seedance-test",
                "prompt": "Use Video 1",
                "reference_urls": [
                    {
                        "url": reference["url"],
                        "media_type": "video",
                        "role": "reference_video",
                        "real_human": True,
                    }
                ],
            },
        )
        assert created.status_code == 200
        local_id = created.json()["id"]
        assert local_id.startswith("video-rh-")

        for _ in range(100):
            status = await client.get(f"/v1/videos/{local_id}")
            if status.json()["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        assert status.json()["status"] == "completed"

    actions = [request.url.params["Action"] for request in asset_requests]
    assert [action for action in actions if action != "ListAssets"] == [
        "CreateAsset",
        "GetAsset",
        "DeleteAsset",
    ]
    create_request = next(
        request
        for request in asset_requests
        if request.url.params["Action"] == "CreateAsset"
    )
    create_body = json.loads(create_request.content)
    assert create_body["GroupId"] == "group-person"
    assert create_body["AssetType"] == "Video"
    assert "Credential=ak-test/" in create_request.headers["authorization"]
    video_payload = json.loads(
        next(r.content for r in ark_requests if r.method == "POST")
    )
    assert video_payload["content"][1] == {
        "type": "video_url",
        "video_url": {"url": "asset://asset-temporary"},
        "role": "reference_video",
    }
    assert not list(settings.media_dir.glob("*.mp4"))


@pytest.mark.asyncio
async def test_real_human_reference_requires_asset_credentials(settings: Settings):
    app = create_app(settings, ark_transport=ark_transport([]))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post(
            "/v1/videos",
            json={
                "model": "seedance-test",
                "prompt": "test",
                "reference_urls": [
                    {
                        "url": "https://example.com/me.mp4",
                        "media_type": "video",
                        "real_human": True,
                    }
                ],
            },
        )
    assert response.status_code == 400
    assert "BYTEPLUS_ACCESS_KEY_ID" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_real_human_configuration_reports_missing_credentials(settings: Settings):
    app = create_app(settings, ark_transport=ark_transport([]))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.get("/v1/real-human/configuration")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "verified": False}


@pytest.mark.asyncio
async def test_real_human_jobs_are_backgrounded_and_concurrency_is_bounded(
    settings: Settings,
):
    settings.byteplus_access_key_id = "ak-test"
    settings.byteplus_secret_access_key = "sk-test"
    settings.byteplus_asset_group_id = "group-person"
    settings.asset_worker_concurrency = 4
    settings.asset_maintenance_interval_seconds = 0.005
    settings.asset_poll_interval_seconds = 0.001
    active_creates = 0
    max_active_creates = 0
    asset_counter = 0

    async def asset_handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_creates, max_active_creates, asset_counter
        action = request.url.params["Action"]
        if action == "ListAssets":
            return httpx.Response(200, json={"Result": {"Items": [], "TotalCount": 0}})
        if action == "CreateAsset":
            asset_counter += 1
            asset_id = f"asset-parallel-{asset_counter}"
            active_creates += 1
            max_active_creates = max(max_active_creates, active_creates)
            await asyncio.sleep(0.03)
            active_creates -= 1
            return httpx.Response(200, json={"Result": {"Id": asset_id}})
        if action == "GetAsset":
            body = json.loads(request.content)
            return httpx.Response(
                200, json={"Result": {"Id": body["Id"], "Status": "Active"}}
            )
        if action == "DeleteAsset":
            return httpx.Response(200, json={"Result": {}})
        raise AssertionError(action)

    provider_counter = 0

    def provider_handler(request: httpx.Request) -> httpx.Response:
        nonlocal provider_counter
        if request.method == "POST":
            provider_counter += 1
            return httpx.Response(200, json={"id": f"cgt-rh-{provider_counter}"})
        task_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"id": task_id, "status": "succeeded"})

    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(provider_handler),
        asset_transport=httpx.MockTransport(asset_handler),
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        created = await asyncio.gather(
            *(
                client.post(
                    "/v1/videos",
                    json={
                        "model": "seedance-test",
                        "prompt": f"Edit Video 1, request {index}",
                        "reference_urls": [
                            {
                                "url": f"https://example.com/person-{index}.mp4",
                                "media_type": "video",
                                "real_human": True,
                            }
                        ],
                    },
                )
                for index in range(8)
            )
        )
        health = await client.get("/health")
        ids = [response.json()["id"] for response in created]
        assert all(response.status_code == 200 for response in created)
        assert health.status_code == 200

        for _ in range(200):
            statuses = await asyncio.gather(
                *(client.get(f"/v1/videos/{job_id}") for job_id in ids)
            )
            if all(response.json()["status"] == "completed" for response in statuses):
                break
            await asyncio.sleep(0.01)

    assert all(response.json()["status"] == "completed" for response in statuses)
    assert max_active_creates == 4
