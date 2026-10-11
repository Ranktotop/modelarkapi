"""Kling video-commerce solutions (T21)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()
CDN = "v1-kling.klingai.com"
VIDEO = b"\x00\x00\x00\x20ftypisomcommerce"
JPEG = b"\xff\xd8\xff" + b"\x00" * 16


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == CDN:
            return httpx.Response(
                200, content=VIDEO if request.url.path.endswith(".mp4") else JPEG
            )
        if request.method == "POST":
            return httpx.Response(
                200, json={"code": 0, "data": {"id": "n1", "status": "submitted"}}
            )
        assert request.url.path == "/solutions"
        assert request.url.params["task_ids"] == "n1"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": [
                    {
                        "id": "n1",
                        "status": "succeeded",
                        "outputs": [
                            {
                                "type": "product_video",
                                "url": f"https://{CDN}/v.mp4",
                                "duration": "12",
                            },
                            {"type": "product_image", "url": f"https://{CDN}/p.jpg"},
                        ],
                    }
                ],
            },
        )

    def posted(self) -> tuple[str, dict[str, Any]]:
        request = next(r for r in self.requests if r.method == "POST")
        return request.url.path, json.loads(request.content)


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        kling_api_key="kling-key",
        public_base_url="https://proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
    )


async def run(tmp_path: Path, fake: FakeKling, *calls):
    app = create_app(
        settings_for(tmp_path),
        kling_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        results = []
        for call in calls:
            results.append(await call(client, results))
        return results


def create(body: dict[str, Any]):
    return lambda client, _: client.post(
        "/v1/videos", json={"model": "kling-commerce", **body}
    )


async def test_talking_agent_creator_mode(tmp_path: Path):
    fake = FakeKling()

    (response,) = await run(
        tmp_path,
        fake,
        create(
            {
                "task": "commerce_talking_agent",
                "references": [{"type": "image", "url": PNG_URI, "role": "avatar"}],
                "speech": {"voice": "female_warm_rich"},
                "commerce": {
                    "script": "Hi, today I show you my favourite mug.",
                    "speech_rate": 1.2,
                },
            }
        ),
    )

    assert response.status_code == 200
    path, body = fake.posted()
    assert path == "/solutions/talking_agent"
    assert body == {
        "contents": [
            {"type": "avatar_image", "url": PNG_B64},
            {"type": "speech_script", "text": "Hi, today I show you my favourite mug."},
        ],
        "settings": {
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "voice_id": "female_warm_rich",
            "speech_rate": 1.2,
        },
    }


async def test_talking_agent_product_mode(tmp_path: Path):
    fake = FakeKling()

    (response,) = await run(
        tmp_path,
        fake,
        create(
            {
                "task": "commerce_talking_agent",
                "prompt": "points at the product",
                "references": [
                    {
                        "type": "image",
                        "url": "https://images.example.com/mug.png",
                        "role": "product",
                    }
                ],
                "commerce": {
                    "avatar_id": "avatar_eva_female",
                    "title": "Mug",
                    "price": "12 EUR",
                    "selling_points": ["dishwasher safe", "500 ml"],
                    "script": "Look at this mug.",
                    "bgm": True,
                },
            }
        ),
    )

    assert response.status_code == 200
    _, body = fake.posted()
    assert body["contents"] == [
        {"type": "avatar_id", "text": "avatar_eva_female"},
        {"type": "ref_image", "url": "https://images.example.com/mug.png"},
        {"type": "goods_title", "text": "Mug"},
        {"type": "goods_price", "text": "12 EUR"},
        {"type": "goods_selling_point", "text": "dishwasher safe"},
        {"type": "goods_selling_point", "text": "500 ml"},
        {"type": "speech_script", "text": "Look at this mug."},
    ]
    assert body["settings"] == {
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "action_prompt": "points at the product",
        "bgm_enabled": True,
    }


@pytest.mark.parametrize(
    "body",
    [
        {
            "references": [{"type": "image", "url": PNG_URI, "role": "avatar"}],
            "commerce": {"script": "x"},
        },
        {
            "references": [{"type": "image", "url": PNG_URI, "role": "avatar"}],
            "speech": {"voice": "female_warm_rich"},
            "commerce": {"script": "x", "avatar_id": "avatar_eva_female"},
        },
        {"commerce": {"avatar_id": "avatar_eva_female"}},
        {"commerce": {"avatar_id": "avatar_eva_female", "script": "x", "title": "Mug"}},
        {
            "references": [{"type": "image", "url": PNG_URI, "role": "product"}],
            "commerce": {
                "avatar_id": "avatar_eva_female",
                "script": "x",
                "title": "Mug",
                "speech_rate": 1.2,
            },
        },
    ],
)
async def test_talking_agent_rules(tmp_path: Path, body: dict[str, Any]):
    fake = FakeKling()

    (response,) = await run(
        tmp_path, fake, create({"task": "commerce_talking_agent", **body})
    )

    assert response.status_code == 400
    assert not any(r.method == "POST" for r in fake.requests)


async def test_goods_studio(tmp_path: Path):
    fake = FakeKling()

    accepted, wrong_length, untitled = await run(
        tmp_path,
        fake,
        create(
            {
                "task": "commerce_goods_studio",
                "seconds": 30,
                "aspect_ratio": "1:1",
                "references": [
                    {"type": "image", "url": PNG_URI},
                    {"type": "image", "url": "https://images.example.com/b.png"},
                ],
                "commerce": {"title": "Mug", "description": "A sturdy mug."},
                "watermark": True,
            }
        ),
        create(
            {
                "task": "commerce_goods_studio",
                "seconds": 20,
                "references": [{"type": "image", "url": PNG_URI}],
                "commerce": {"title": "Mug"},
            }
        ),
        create(
            {
                "task": "commerce_goods_studio",
                "references": [{"type": "image", "url": PNG_URI}],
            }
        ),
    )

    assert accepted.status_code == 200
    path, body = fake.posted()
    assert path == "/solutions/e-commerce/goods_studio"
    assert body == {
        "contents": [
            {"type": "ref_image", "url": PNG_B64},
            {"type": "ref_image", "url": "https://images.example.com/b.png"},
            {"type": "goods_title", "text": "Mug"},
            {"type": "goods_description", "text": "A sturdy mug."},
        ],
        "settings": {"resolution": "720p", "aspect_ratio": "1:1", "duration": 30},
        "options": {"watermark": {"enabled": True}},
    }
    assert wrong_length.status_code == 400
    assert untitled.status_code == 400


async def test_apparel_replicator_round_trip(tmp_path: Path):
    fake = FakeKling()

    created, done, video, image = await run(
        tmp_path,
        fake,
        create(
            {
                "task": "commerce_apparel",
                "aspect_ratio": "3:4",
                "references": [
                    {"type": "video", "url": "https://videos.example.com/ref.mp4"},
                    {"type": "image", "url": PNG_URI, "role": "product"},
                    {
                        "type": "image",
                        "url": "https://images.example.com/model.png",
                        "role": "model",
                    },
                    {"type": "audio", "url": "https://audio.example.com/bgm.mp3"},
                ],
                "speech": {"voice": "calm_sales_woman"},
                "commerce": {"product_info": "Breathable linen shirt"},
                "watermark": True,
            }
        ),
        lambda client, results: client.get(f"/v1/videos/{results[0].json()['id']}"),
        lambda client, results: client.get(
            f"/v1/videos/{results[0].json()['id']}/content"
        ),
        lambda client, results: client.get(
            f"/v1/videos/{results[0].json()['id']}/content?variant=product_image_1"
        ),
    )

    assert created.status_code == 200
    path, body = fake.posted()
    assert path == "/solutions/e-commerce/clothing_dupe"
    assert body == {
        "contents": [
            {"type": "product_info", "text": "Breathable linen shirt"},
            {"type": "source_video", "url": "https://videos.example.com/ref.mp4"},
            {"type": "product_image", "url": PNG_B64},
            {"type": "model_image", "url": "https://images.example.com/model.png"},
            {"type": "bgm", "url": "https://audio.example.com/bgm.mp3"},
            {"type": "voice", "voice_id": "calm_sales_woman"},
        ],
        "settings": {"resolution": "720p", "aspect_ratio": "3:4"},
        "options": {"watermark_info": {"enabled": True}},
    }
    assert done.json()["status"] == "completed"
    assert video.content == VIDEO
    assert image.content == JPEG


async def test_commerce_model_is_listed(tmp_path: Path):
    (models,) = await run(
        tmp_path, FakeKling(), lambda client, _: client.get("/v1/models")
    )

    commerce = next(m for m in models.json()["data"] if m["id"] == "kling-commerce")
    assert commerce["virtual"] is True
    assert set(commerce["capabilities"]["tasks"]) == {
        "commerce_talking_agent",
        "commerce_goods_studio",
        "commerce_apparel",
    }
