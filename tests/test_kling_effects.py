"""Kling video effects and multi-element editing (T20)."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from kling_helpers import strip_external

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()
VIDEO_URL = "https://videos.example.com/clip.mp4"


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        ok = lambda data: httpx.Response(200, json={"code": 0, "data": data})
        if request.url.host == "v1-kling.klingai.com":
            return httpx.Response(200, content=b"\x00\x00\x00\x20ftypisom")
        if path == "/v1/videos/multi-elements/init-selection":
            return ok(
                {
                    "session_id": "S1",
                    "fps": 24,
                    "original_duration": 4.2,
                    "total_frame": 100,
                }
            )
        if path == "/v1/videos/multi-elements/add-selection":
            return ok({"session_id": "S1"})
        if request.method == "POST":
            return ok({"task_id": "T1", "task_status": "submitted"})
        return ok(
            {
                "task_id": "T1",
                "task_status": "succeed",
                "task_result": {
                    "videos": [
                        {"id": "kv", "url": "https://v1-kling.klingai.com/r.mp4"}
                    ]
                },
            }
        )

    def posts(self, path: str) -> list[dict[str, Any]]:
        return [
            strip_external(json.loads(r.content))
            for r in self.requests
            if r.method == "POST" and r.url.path == path
        ]


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        kling_api_key="kling-key",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
        provider_poll_interval_seconds=0.01,
    )


async def run(tmp_path: Path, fake: FakeKling, scenario):
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
        return await scenario(client)


async def test_effect_catalogue_lists_every_template(tmp_path: Path):
    async def scenario(client):
        return (await client.get("/v1/providers/kling/effects")).json()

    catalogue = await run(tmp_path, FakeKling(), scenario)

    effects = {effect["id"]: effect for effect in catalogue["data"]}
    assert len(effects) == 219
    assert effects["hug_pro"]["images"] == 2
    assert effects["net_the_fish"]["images"] == 1


async def test_single_image_effect(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client):
        return await client.post(
            "/v1/videos",
            json={
                "model": "kling-effects",
                "effect": "net_the_fish",
                "references": [{"type": "image", "url": PNG_URI}],
            },
        )

    response = await run(tmp_path, fake, scenario)

    assert response.status_code == 200
    assert fake.posts("/v1/videos/effects") == [
        {"effect_scene": "net_the_fish", "input": {"image": PNG_B64}}
    ]


async def test_dual_image_effect(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client):
        return await client.post(
            "/v1/videos",
            json={
                "model": "kling-effects",
                "effect": "hug_pro",
                "references": [
                    {"type": "image", "url": PNG_URI},
                    {"type": "image", "url": "https://images.example.com/b.png"},
                ],
            },
        )

    response = await run(tmp_path, fake, scenario)

    assert response.status_code == 200
    assert fake.posts("/v1/videos/effects")[0]["input"] == {
        "images": [PNG_B64, "https://images.example.com/b.png"]
    }


@pytest.mark.parametrize(
    ("effect", "images", "code"),
    [
        ("hug_pro", 1, "reference_limit"),
        ("net_the_fish", 2, "reference_limit"),
        ("no_such_effect", 1, "unsupported_parameter"),
    ],
)
async def test_effect_rules(tmp_path: Path, effect: str, images: int, code: str):
    fake = FakeKling()

    async def scenario(client):
        return await client.post(
            "/v1/videos",
            json={
                "model": "kling-effects",
                "effect": effect,
                "references": [{"type": "image", "url": PNG_URI}] * images,
            },
        )

    response = await run(tmp_path, fake, scenario)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert fake.posts("/v1/videos/effects") == []


async def test_multi_element_swap_runs_the_selection_session(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client):
        created = await client.post(
            "/v1/videos",
            json={
                "model": "kling-multi-elements",
                "edit_mode": "swap",
                "prompt": "replace the mug with <<<image_1>>>",
                "references": [
                    {"type": "video", "url": VIDEO_URL},
                    {"type": "image", "url": PNG_URI},
                ],
                "selections": [
                    {"frame_index": 0, "points": [{"x": 0.4, "y": 0.5}]},
                    {
                        "frame_index": 50,
                        "points": [{"x": 0.42, "y": 0.52}, {"x": 0.45, "y": 0.5}],
                    },
                ],
                "quality": "pro",
            },
        )
        assert created.status_code == 200
        for _ in range(200):
            body = (await client.get(f"/v1/videos/{created.json()['id']}")).json()
            if body["status"] in {"completed", "failed"}:
                return body
            await asyncio.sleep(0.01)
        raise AssertionError("not finished")

    done = await run(tmp_path, fake, scenario)

    assert done["status"] == "completed"
    assert fake.posts("/v1/videos/multi-elements/init-selection") == [
        {"video_url": VIDEO_URL}
    ]
    assert fake.posts("/v1/videos/multi-elements/add-selection") == [
        {"session_id": "S1", "frame_index": 0, "points": [{"x": 0.4, "y": 0.5}]},
        {
            "session_id": "S1",
            "frame_index": 50,
            "points": [{"x": 0.42, "y": 0.52}, {"x": 0.45, "y": 0.5}],
        },
    ]
    assert fake.posts("/v1/videos/multi-elements") == [
        {
            "session_id": "S1",
            "edit_mode": "swap",
            "image_list": [{"image": PNG_B64}],
            "prompt": "replace the mug with <<<image_1>>>",
            "mode": "pro",
            "duration": "5",
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"edit_mode": "swap", "images": 2},
        {"edit_mode": "removal", "images": 1},
        {"edit_mode": "addition", "images": 0},
        {
            "edit_mode": "swap",
            "images": 1,
            "selections": [
                {"frame_index": i, "points": [{"x": 0.5, "y": 0.5}]} for i in range(11)
            ],
        },
        {
            "edit_mode": "swap",
            "images": 1,
            "selections": [{"frame_index": 0, "points": [{"x": 1.5, "y": 0.5}]}],
        },
    ],
)
async def test_multi_element_rules(tmp_path: Path, body: dict[str, Any]):
    fake = FakeKling()
    request = {
        "model": "kling-multi-elements",
        "prompt": "edit",
        "edit_mode": body["edit_mode"],
        "references": [{"type": "video", "url": VIDEO_URL}]
        + [{"type": "image", "url": PNG_URI}] * body["images"],
        "selections": body.get(
            "selections", [{"frame_index": 0, "points": [{"x": 0.5, "y": 0.5}]}]
        ),
    }

    async def scenario(client):
        return await client.post("/v1/videos", json=request)

    response = await run(tmp_path, fake, scenario)

    assert response.status_code == 400
    assert not any(r.method == "POST" for r in fake.requests)
