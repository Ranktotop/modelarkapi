"""Seedance behind the unified request contract (T22, research/seedance.md §13)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import encode_video_id

MODEL = "dreamina-seedance-2-5-260628"
SOURCE_VIDEO = "https://ark-content-generation-ap-southeast-1.tos.example.com/src.mp4"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()


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
    def __init__(self, source_status: str = "succeeded") -> None:
        self.created: list[dict[str, Any]] = []
        self.source_status = source_status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            self.created.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "cgt-new"})
        return httpx.Response(
            200,
            json={
                "id": request.url.path.rsplit("/", 1)[-1],
                "model": MODEL,
                "status": self.source_status,
                "resolution": "480p",
                "ratio": "16:9",
                "duration": 4,
                "content": {"video_url": SOURCE_VIDEO},
            },
        )


async def post(settings: Settings, fake: FakeArk, path: str, body: dict[str, Any]):
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
        return await client.post(path, json=body)


async def test_edit_endpoint_sends_the_source_video_as_edit(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos/edits",
        {
            "model": MODEL,
            "prompt": "make it snow",
            "video": {"id": encode_video_id("cgt-source", MODEL)},
        },
    )

    assert response.status_code == 200, response.text
    payload = fake.created[0]
    assert payload["omni_reference_task_type"] == "edit"
    assert payload["ratio"] == "adaptive"
    assert payload["duration"] == -1
    assert payload["content"] == [
        {"type": "text", "text": "make it snow"},
        {
            "type": "video_url",
            "video_url": {"url": SOURCE_VIDEO},
            "role": "reference_video",
        },
    ]


async def test_edit_of_an_unfinished_task_is_rejected(settings: Settings):
    fake = FakeArk(source_status="running")

    response = await post(
        settings,
        fake,
        "/v1/videos/extensions",
        {"model": MODEL, "prompt": "continue", "video": {"id": "cgt-source"}},
    )

    assert response.status_code == 400
    assert not fake.created


async def test_unified_references_and_parameters_reach_modelark(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": MODEL,
            "prompt": "the fox from image 1 runs",
            "seconds": "auto",
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "references": [
                {"type": "image", "url": PNG_URI},
                {"type": "audio", "url": "https://audio.example.com/a.mp3"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = fake.created[0]
    assert payload["duration"] == -1
    assert payload["ratio"] == "9:16"
    assert payload["resolution"] == "1080p"
    assert "omni_reference_task_type" not in payload
    assert payload["content"][1:] == [
        {"type": "image_url", "image_url": {"url": PNG_URI}, "role": "reference_image"},
        {
            "type": "audio_url",
            "audio_url": {"url": "https://audio.example.com/a.mp3"},
            "role": "reference_audio",
        },
    ]


async def test_single_image_becomes_the_first_frame(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": MODEL,
            "prompt": "wind",
            "references": [{"type": "image", "url": "https://img.example.com/a.png"}],
        },
    )

    assert response.status_code == 200, response.text
    assert fake.created[0]["content"][1]["role"] == "first_frame"
    assert fake.created[0]["ratio"] == "adaptive"


async def test_stitch_extends_several_clips(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": MODEL,
            "prompt": "video 1 flows into video 2",
            "task": "stitch",
            "references": [
                {"type": "video", "url": "https://v.example.com/1.mp4"},
                {"type": "video", "url": "https://v.example.com/2.mp4"},
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = fake.created[0]
    assert payload["omni_reference_task_type"] == "extend"
    assert [item["role"] for item in payload["content"][1:]] == [
        "reference_video",
        "reference_video",
    ]


async def test_inline_video_is_rehosted_because_modelark_wants_a_url(
    settings: Settings,
):
    fake = FakeArk()
    video = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 32

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": MODEL,
            "prompt": "restyle",
            "task": "edit",
            "references": [
                {
                    "type": "video",
                    "url": "data:video/mp4;base64," + base64.b64encode(video).decode(),
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    url = fake.created[0]["content"][1]["video_url"]["url"]
    assert url.startswith("https://proxy.example.com/media/reference/")


async def test_unsupported_unified_task_is_rejected(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": "seedance-1-0-pro-250528",
            "prompt": "x",
            "task": "edit",
            "references": [{"type": "video", "url": "https://v.example.com/1.mp4"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_task"
    assert not fake.created


async def test_draft_then_final_video(settings: Settings):
    fake = FakeArk()

    draft = await post(
        settings, fake, "/v1/videos", {"model": MODEL, "prompt": "fox", "draft": True}
    )
    final = await post(
        settings,
        fake,
        "/v1/videos",
        {"model": MODEL, "draft_task_id": encode_video_id("cgt-draft", MODEL)},
    )

    assert draft.status_code == 200, draft.text
    assert fake.created[0]["draft"] is True
    assert fake.created[0]["resolution"] == "480p"
    assert final.status_code == 200, final.text
    assert fake.created[1] == {
        "model": MODEL,
        "content": [{"type": "draft_task", "draft_task": {"id": "cgt-draft"}}],
        "resolution": "1080p",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"model": MODEL, "prompt": "fox", "draft": True, "resolution": "720p"},
        {"model": "dreamina-seedance-2-0-260128", "prompt": "fox", "draft": True},
        {"model": MODEL, "draft_task_id": "cgt-draft", "prompt": "again"},
        {"model": MODEL, "draft_task_id": "cgt-draft", "seconds": 5},
        {"model": MODEL, "draft_task_id": "cgt-draft", "resolution": "720p"},
    ],
)
async def test_draft_rules(settings: Settings, body: dict[str, Any]):
    fake = FakeArk()

    response = await post(settings, fake, "/v1/videos", body)

    assert response.status_code == 400
    assert not fake.created


async def test_audio_flag_only_for_models_that_know_it(settings: Settings):
    fake = FakeArk()

    plain = await post(
        settings,
        fake,
        "/v1/videos",
        {"model": "seedance-1-0-pro-250528", "prompt": "fox"},
    )
    explicit = await post(
        settings,
        fake,
        "/v1/videos",
        {"model": "seedance-1-0-pro-250528", "prompt": "fox", "generate_audio": True},
    )

    assert plain.status_code == 200, plain.text
    assert "generate_audio" not in fake.created[0]
    assert explicit.status_code == 400


async def test_public_asset_ids_become_asset_uris(settings: Settings):
    fake = FakeArk()

    response = await post(
        settings,
        fake,
        "/v1/videos",
        {
            "model": MODEL,
            "prompt": "the character waves",
            "references": [{"type": "image", "asset_id": "asset-20261011-abc"}],
            "task": "reference_to_video",
        },
    )

    assert response.status_code == 200, response.text
    assert fake.created[0]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "asset://asset-20261011-abc"},
        "role": "reference_image",
    }


async def test_remix_keeps_the_source_resolution(settings: Settings):
    fake = FakeArk()
    source = encode_video_id("cgt-source", MODEL)

    kept = await post(
        settings, fake, f"/v1/videos/{source}/remix", {"prompt": "make it snow"}
    )
    chosen = await post(
        settings,
        fake,
        f"/v1/videos/{source}/remix",
        {"prompt": "make it snow", "resolution": "1080p"},
    )

    assert kept.status_code == 200, kept.text
    assert fake.created[0]["resolution"] == "480p"
    assert chosen.status_code == 200, chosen.text
    assert fake.created[1]["resolution"] == "1080p"
