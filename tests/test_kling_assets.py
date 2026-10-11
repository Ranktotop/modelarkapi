"""Kling elements and voices, their use in generations, and native routes (T17)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 24
WAV_URI = "data:audio/wav;base64," + base64.b64encode(WAV).decode()


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        ok = lambda data: httpx.Response(
            200, json={"code": 0, "message": "SUCCEED", "data": data}
        )  # noqa: E731
        if path == "/v1/general/advanced-custom-elements" and request.method == "POST":
            return ok({"task_id": "E1", "task_status": "submitted"})
        if path == "/v1/general/advanced-custom-elements/E1":
            return ok(
                {
                    "task_id": "E1",
                    "task_status": "succeed",
                    "task_result": {
                        "elements": [
                            {
                                "element_id": 123,
                                "element_name": "Hero",
                                "status": "succeed",
                            }
                        ]
                    },
                }
            )
        if path == "/v1/general/advanced-custom-elements":
            return ok(
                [
                    {
                        "task_id": "E1",
                        "task_status": "succeed",
                        "task_result": {
                            "elements": [{"element_id": 123, "element_name": "Hero"}]
                        },
                    },
                    {"task_id": "E2", "task_status": "processing", "task_result": {}},
                ]
            )
        if path == "/v1/general/advanced-presets-elements":
            return ok(
                [
                    {
                        "task_id": "P",
                        "task_status": "succeed",
                        "task_result": {
                            "elements": [{"element_id": 9, "element_name": "Robot"}]
                        },
                    }
                ]
            )
        if path == "/v1/general/custom-voices" and request.method == "POST":
            return ok({"task_id": "V1", "task_status": "submitted"})
        if path in {
            "/v1/general/delete-advanced-elements",
            "/v1/general/delete-voices",
        }:
            return ok({})
        if path == "/v1/general/presets-voices":
            return ok(
                [
                    {
                        "task_id": "PV",
                        "task_status": "succeed",
                        "task_result": {
                            "voices": [{"voice_id": "v-9", "voice_name": "Narrator"}]
                        },
                    }
                ]
            )
        if path.startswith("/v1/videos/") and request.method == "POST":
            return ok({"task_id": "T1", "task_status": "submitted"})
        if path.startswith("/v1/videos/"):
            return ok({"task_id": "T1", "task_status": "processing"})
        return httpx.Response(404, json={"code": 1202, "message": "unexpected"})

    def posted(self, path: str) -> dict[str, Any]:
        return next(
            json.loads(r.content)
            for r in self.requests
            if r.method == "POST" and r.url.path == path
        )


def settings_for(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        kling_api_key="kling-key",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
        **extra,
    )


async def run(settings: Settings, fake: FakeKling, *calls):
    app = create_app(
        settings,
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


async def test_elements_are_created_and_become_ready(tmp_path: Path):
    fake = FakeKling()

    created, ready = await run(
        settings_for(tmp_path),
        fake,
        lambda c, _: c.post(
            "/v1/assets",
            json={
                "provider": "kling",
                "type": "element",
                "name": "Hero",
                "description": "Our main character",
                "references": [
                    {"type": "image", "url": PNG_URI, "role": "frontal"},
                    {"type": "image", "url": "https://images.example.com/side.png"},
                ],
                "tags": ["o_102"],
            },
        ),
        lambda c, results: c.get(f"/v1/assets/{results[0].json()['id']}"),
    )

    assert created.status_code == 200
    assert created.json()["status"] == "processing"
    assert fake.posted("/v1/general/advanced-custom-elements") == {
        "element_name": "Hero",
        "element_description": "Our main character",
        "reference_type": "image_refer",
        "element_image_list": {
            "frontal_image": PNG_B64,
            "refer_images": [{"image_url": "https://images.example.com/side.png"}],
        },
        "tag_list": [{"tag_id": "o_102"}],
    }
    assert ready.json()["status"] == "ready"
    assert ready.json()["id"] == "asset-kling-element-123"
    assert ready.json()["name"] == "Hero"


async def test_assets_are_listed_per_scope(tmp_path: Path):
    custom, presets, voices = await run(
        settings_for(tmp_path),
        FakeKling(),
        lambda c, _: c.get(
            "/v1/assets", params={"provider": "kling", "type": "element"}
        ),
        lambda c, _: c.get(
            "/v1/assets",
            params={"provider": "kling", "type": "element", "scope": "preset"},
        ),
        lambda c, _: c.get(
            "/v1/assets",
            params={"provider": "kling", "type": "voice", "scope": "preset"},
        ),
    )

    assert [(a["id"], a["status"]) for a in custom.json()["data"]] == [
        ("asset-kling-element-123", "ready"),
        ("asset-kling-element-task-E2", "processing"),
    ]
    assert [a["id"] for a in presets.json()["data"]] == ["asset-kling-element-9"]
    assert voices.json()["data"][0]["id"] == "asset-kling-voice-v-9"
    assert voices.json()["data"][0]["name"] == "Narrator"


async def test_assets_are_deleted_by_id(tmp_path: Path):
    fake = FakeKling()

    deleted, voice = await run(
        settings_for(tmp_path),
        fake,
        lambda c, _: c.delete("/v1/assets/asset-kling-element-123"),
        lambda c, _: c.delete("/v1/assets/asset-kling-voice-v-1"),
    )

    assert deleted.json() == {
        "id": "asset-kling-element-123",
        "object": "asset.deleted",
        "deleted": True,
    }
    assert fake.posted("/v1/general/delete-advanced-elements") == {"element_id": "123"}
    assert fake.posted("/v1/general/delete-voices") == {"voice_id": "v-1"}
    assert voice.status_code == 200


async def test_voices_from_uploads_need_a_public_url(tmp_path: Path):
    body = {
        "provider": "kling",
        "type": "voice",
        "name": "Me",
        "references": [{"type": "audio", "url": WAV_URI}],
    }

    (missing,) = await run(
        settings_for(tmp_path),
        FakeKling(),
        lambda c, _: c.post("/v1/assets", json=body),
    )
    fake = FakeKling()
    (created,) = await run(
        settings_for(tmp_path, public_base_url="https://proxy.example.com"),
        fake,
        lambda c, _: c.post("/v1/assets", json=body),
    )

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "public_base_url_required"
    assert created.status_code == 200
    voice_url = fake.posted("/v1/general/custom-voices")["voice_url"]
    assert voice_url.startswith("https://proxy.example.com/media/reference/")


async def test_elements_are_used_in_kling_3_image_to_video(tmp_path: Path):
    fake = FakeKling()

    (created,) = await run(
        settings_for(tmp_path),
        fake,
        lambda c, _: c.post(
            "/v1/videos",
            json={
                "model": "kling-3.0",
                "prompt": "@Hero waves",
                "references": [
                    {"type": "image", "url": PNG_URI, "role": "first_frame"},
                    {"asset_id": "asset-kling-element-123"},
                ],
            },
        ),
    )

    assert created.status_code == 200
    assert fake.posted("/v1/videos/image2video")["element_list"] == [
        {"element_id": 123}
    ]


async def test_voices_turn_on_sound_at_1080p_on_kling_2_6(tmp_path: Path):
    fake = FakeKling()

    (created,) = await run(
        settings_for(tmp_path),
        fake,
        lambda c, _: c.post(
            "/v1/videos",
            json={
                "model": "kling-2.6",
                "prompt": "she says hello",
                "references": [
                    {"type": "image", "url": PNG_URI, "role": "first_frame"},
                    {"asset_id": "asset-kling-voice-829837252279803904"},
                ],
            },
        ),
    )

    assert created.status_code == 200
    body = fake.posted("/v1/videos/image2video")
    # Voice IDs are numeric strings and must stay strings.
    assert body["voice_list"] == [{"voice_id": "829837252279803904"}]
    assert body["sound"] == "on"
    assert body["mode"] == "pro"


async def test_elements_and_voices_cannot_be_combined(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path),
        FakeKling(),
        lambda c, _: c.post(
            "/v1/videos",
            json={
                "model": "kling-3.0",
                "prompt": "x",
                "references": [
                    {"type": "image", "url": PNG_URI, "role": "first_frame"},
                    {"asset_id": "asset-kling-element-123"},
                    {"asset_id": "asset-kling-voice-v-1"},
                ],
            },
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reference_limit"


async def test_native_routes_pass_through_and_register_video_tasks(tmp_path: Path):
    fake = FakeKling()

    voices, created, status, forbidden = await run(
        settings_for(tmp_path),
        fake,
        lambda c, _: c.get(
            "/v1/providers/kling/v1/general/presets-voices", params={"pageNum": 1}
        ),
        lambda c, _: c.post(
            "/v1/providers/kling/v1/videos/text2video",
            json={"model_name": "kling-v3", "prompt": "fox", "duration": "5"},
        ),
        lambda c, results: c.get(results[1].json()["proxy"]["status_url"]),
        lambda c, _: c.post("/v1/providers/kling/v1/images/generations", json={}),
    )

    assert voices.json()["data"][0]["task_result"]["voices"][0]["voice_id"] == "v-9"
    forwarded = next(
        r for r in fake.requests if r.url.path == "/v1/general/presets-voices"
    )
    assert forwarded.url.params["pageNum"] == "1"
    assert created.json()["data"]["task_id"] == "T1"
    assert fake.posted("/v1/videos/text2video") == {
        "model_name": "kling-v3",
        "prompt": "fox",
        "duration": "5",
    }
    assert status.json()["status"] == "in_progress"
    assert forbidden.status_code == 404
