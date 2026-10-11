"""OpenAI characters as aliases of Kling video elements (SPEC 2.1, 3.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_character_id

MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        def ok(data: Any) -> httpx.Response:
            return httpx.Response(
                200, json={"code": 0, "message": "SUCCEED", "data": data}
            )
        if path == "/v1/general/advanced-custom-elements" and request.method == "POST":
            return ok({"task_id": "E1", "task_status": "submitted"})
        if path == "/v1/general/advanced-custom-elements/E1":
            return ok(
                {
                    "task_id": "E1",
                    "task_status": "succeed",
                    "task_result": {
                        "elements": [{"element_id": 123, "element_name": "Mia"}]
                    },
                }
            )
        return ok({"task_id": "t1", "task_status": "submitted"})

    def posted(self, path: str) -> dict[str, Any]:
        return json.loads(
            next(
                r for r in self.requests if r.method == "POST" and r.url.path == path
            ).content
        )


async def test_characters_are_kling_video_elements(tmp_path: Path):
    fake = FakeKling()
    app = create_app(
        Settings(
            kling_api_key="kling-key",
            proxy_api_key=None,
            require_proxy_api_key=False,
            public_base_url="https://proxy.example.com",
            media_dir=tmp_path / "media",
            asset_job_db=tmp_path / "asset-jobs.db",
            provider_job_db=tmp_path / "provider-jobs.db",
            output_dir=tmp_path / "outputs",
        ),
        kling_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        created = await client.post(
            "/v1/videos/characters",
            data={"name": "Mia"},
            files={"video": ("mia.mp4", MP4, "video/mp4")},
        )
        fetched = await client.get(f"/v1/videos/characters/{created.json()['id']}")
        used = await client.post(
            "/v1/videos",
            json={
                "model": "kling-3.0-omni",
                "prompt": "<<<element_1>>> waves",
                "references": [{"asset_id": "char-kling-element-123"}],
            },
        )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["id"].startswith("character_")
    assert decode_character_id(body["id"]) == "char-kling-element-task-E1"
    assert body["object"] == "character"
    assert body["name"] == "Mia"
    element = fake.posted("/v1/general/advanced-custom-elements")
    assert element["element_name"] == "Mia"
    assert element["reference_type"] == "video_refer"
    video_url = element["element_video_list"]["refer_videos"][0]["video_url"]
    assert video_url.startswith("https://proxy.example.com/media/reference/")
    assert decode_character_id(fetched.json()["id"]) == "char-kling-element-123"
    assert fetched.json()["status"] == "ready"
    assert used.status_code == 200, used.text
    generation = next(
        json.loads(r.content)
        for r in fake.requests
        if r.method == "POST" and "omni" in r.url.path
    )
    assert generation["element_list"] == [{"element_id": 123}]
