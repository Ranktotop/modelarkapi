"""Kling text-to-video, image-to-video, multi-shot, and audio (T14)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_video_id

KLING_HOST = "api-singapore.klingai.com"
RESULT_URL = "https://v1-kling.klingai.com/result/video.mp4"
VIDEO = b"\x00\x00\x00\x20ftypisomkling-video"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()


def legacy(status: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"task_id": "t1", "task_status": status, **extra}
    if status == "succeed":
        data["task_result"] = {
            "videos": [{"id": "v1", "url": RESULT_URL, "duration": "5.04"}]
        }
    return {"code": 0, "message": "SUCCEED", "data": data}


class FakeKling:
    def __init__(self, states: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.states = states or [legacy("submitted")]
        self.create_response: tuple[int, dict[str, Any]] | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.url.host == "v1-kling.klingai.com":
            return httpx.Response(
                200, content=VIDEO, headers={"content-type": "video/mp4"}
            )
        assert request.headers["authorization"] == "Bearer kling-key"
        if request.method == "POST":
            if self.create_response:
                status, body = self.create_response
                return httpx.Response(status, json=body)
            if path.startswith("/v1/"):
                return httpx.Response(200, json=legacy("submitted"))
            return httpx.Response(
                200, json={"code": 0, "data": {"id": "n1", "status": "submitted"}}
            )
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return httpx.Response(200, json=state)

    def created(self) -> dict[str, Any]:
        return next(json.loads(r.content) for r in self.requests if r.method == "POST")

    def created_path(self) -> str:
        return next(r.url.path for r in self.requests if r.method == "POST")


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
    return lambda client, _: client.post("/v1/videos", json=body)


def follow(path: str = ""):
    return lambda client, results: client.get(
        f"/v1/videos/{results[0].json()['id']}{path}"
    )


async def test_kling_models_are_listed_with_their_limits(tmp_path: Path):
    (models,) = await run(tmp_path, FakeKling(), lambda c, _: c.get("/v1/models"))

    by_id = {m["id"]: m["capabilities"] for m in models.json()["data"]}
    assert {"kling-3.0-turbo", "kling-3.0", "kling-2.6", "kling-2.5-turbo"} <= set(
        by_id
    )
    assert by_id["kling-3.0"]["parameters"]["seconds"]["values"] == list(range(3, 16))
    assert "4k" in by_id["kling-3.0"]["parameters"]["resolution"]["values"]
    assert by_id["kling-2.6"]["parameters"]["seconds"]["values"] == [5, 10]
    assert "multi_shot" in by_id["kling-3.0"]["tasks"]
    assert "first_last_frame" not in by_id["kling-3.0-turbo"]["tasks"]
    assert "generate_audio" not in by_id["kling-2.5-turbo"]["parameters"]


async def test_text_to_video_uses_the_legacy_endpoint_and_stores_the_result(
    tmp_path: Path,
):
    fake = FakeKling([legacy("processing"), legacy("succeed")])

    created, running, done, content = await run(
        tmp_path,
        fake,
        create(
            {
                "model": "kling-3.0",
                "prompt": "a fox",
                "negative_prompt": "blur",
                "seconds": 6,
                "resolution": "1080p",
                "aspect_ratio": "9:16",
                "generate_audio": True,
            }
        ),
        follow(),
        follow(),
        follow("/content"),
    )

    assert created.status_code == 200
    assert decode_video_id(created.json()["id"]).startswith("vid-kling-")
    assert fake.created_path() == "/v1/videos/text2video"
    assert fake.created() == {
        "model_name": "kling-v3",
        "prompt": "a fox",
        "negative_prompt": "blur",
        "duration": "6",
        "mode": "pro",
        "aspect_ratio": "9:16",
        "sound": "on",
    }
    polls = [r for r in fake.requests if r.method == "GET" and r.url.host == KLING_HOST]
    assert polls[0].url.path == "/v1/videos/text2video/t1"
    assert running.json()["status"] == "in_progress"
    assert done.json()["status"] == "completed"
    assert content.content == VIDEO


async def test_quality_pro_selects_1080p(tmp_path: Path):
    fake = FakeKling()

    await run(
        tmp_path,
        fake,
        create({"model": "kling-2.5-turbo", "prompt": "x", "quality": "pro"}),
    )

    assert fake.created()["mode"] == "pro"


async def test_turbo_uses_the_new_api(tmp_path: Path):
    succeeded = {
        "code": 0,
        "data": [
            {
                "id": "n1",
                "status": "succeeded",
                "outputs": [{"type": "video", "url": RESULT_URL}],
            }
        ],
    }
    fake = FakeKling([succeeded])

    _, done = await run(
        tmp_path,
        fake,
        create({"model": "kling-3.0-turbo", "prompt": "a fox", "seconds": 4}),
        follow(),
    )

    assert fake.created_path() == "/text-to-video/kling-3.0-turbo"
    assert fake.created() == {
        "prompt": "a fox",
        "settings": {"resolution": "720p", "aspect_ratio": "16:9", "duration": 4},
    }
    poll = next(
        r for r in fake.requests if r.method == "GET" and r.url.host == KLING_HOST
    )
    assert poll.url.path == "/tasks"
    assert poll.url.params["task_ids"] == "n1"
    assert done.json()["status"] == "completed"


async def test_new_api_task_lists_may_be_nested_under_result(tmp_path: Path):
    nested = {
        "code": 0,
        "data": {
            "result": [
                {
                    "id": "n1",
                    "status": "succeeded",
                    "outputs": [{"type": "video", "url": RESULT_URL}],
                }
            ]
        },
    }

    _, done = await run(
        tmp_path,
        FakeKling([nested]),
        create({"model": "kling-3.0-turbo", "prompt": "a fox"}),
        follow(),
    )

    assert done.json()["status"] == "completed"


async def test_image_to_video_sends_raw_base64_without_aspect_ratio(tmp_path: Path):
    fake = FakeKling()

    (created,) = await run(
        tmp_path,
        fake,
        create(
            {
                "model": "kling-2.6",
                "prompt": "wake up",
                "references": [{"type": "image", "url": PNG_URI}],
            }
        ),
    )

    assert created.status_code == 200
    assert fake.created_path() == "/v1/videos/image2video"
    body = fake.created()
    assert body["image"] == PNG_B64
    assert "aspect_ratio" not in body


async def test_external_image_urls_are_passed_through(tmp_path: Path):
    fake = FakeKling()

    await run(
        tmp_path,
        fake,
        create(
            {
                "model": "kling-3.0",
                "prompt": "morph",
                "references": [
                    {
                        "type": "image",
                        "url": "https://images.example.com/a.png",
                        "role": "first_frame",
                    },
                    {
                        "type": "image",
                        "url": "https://images.example.com/b.png",
                        "role": "last_frame",
                    },
                ],
            }
        ),
    )

    body = fake.created()
    assert body["image"] == "https://images.example.com/a.png"
    assert body["image_tail"] == "https://images.example.com/b.png"


async def test_first_last_frame_on_older_models_needs_1080p(tmp_path: Path):
    frames = [
        {"type": "image", "url": PNG_URI, "role": "first_frame"},
        {"type": "image", "url": PNG_URI, "role": "last_frame"},
    ]

    rejected, accepted = await run(
        tmp_path,
        FakeKling(),
        create(
            {
                "model": "kling-2.5-turbo",
                "prompt": "x",
                "resolution": "720p",
                "references": frames,
            }
        ),
        create({"model": "kling-2.5-turbo", "prompt": "x", "references": frames}),
    )

    assert rejected.status_code == 400
    assert accepted.status_code == 200


async def test_multi_shot_maps_to_legacy_multi_prompt(tmp_path: Path):
    fake = FakeKling()

    (created,) = await run(
        tmp_path,
        fake,
        create(
            {
                "model": "kling-3.0",
                "shots": [
                    {"prompt": "a door opens", "seconds": 2},
                    {"prompt": "a cat walks in", "seconds": 3},
                ],
            }
        ),
    )

    assert created.status_code == 200
    body = fake.created()
    assert body["multi_shot"] is True
    assert body["shot_type"] == "customize"
    assert body["multi_prompt"] == [
        {"index": 1, "prompt": "a door opens", "duration": "2"},
        {"index": 2, "prompt": "a cat walks in", "duration": "3"},
    ]
    assert body["duration"] == "5"
    assert "prompt" not in body


async def test_turbo_multi_shot_uses_the_prompt_syntax(tmp_path: Path):
    fake = FakeKling()

    await run(
        tmp_path,
        fake,
        create(
            {
                "model": "kling-3.0-turbo",
                "shots": [{"prompt": "a", "seconds": 2}, {"prompt": "b", "seconds": 2}],
            }
        ),
    )

    body = fake.created()
    assert body["prompt"] == "shot 1, 2, a; shot 2, 2, b;"
    assert body["settings"]["duration"] == 4


async def test_shot_durations_must_add_up(tmp_path: Path):
    (response,) = await run(
        tmp_path,
        FakeKling(),
        create(
            {
                "model": "kling-3.0",
                "seconds": 8,
                "shots": [{"prompt": "a", "seconds": 2}],
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "shots"


@pytest.mark.parametrize(
    ("body", "param"),
    [
        ({"model": "kling-2.6", "seconds": 7}, "seconds"),
        (
            {"model": "kling-2.6", "generate_audio": True, "resolution": "720p"},
            "resolution",
        ),
        ({"model": "kling-3.0-turbo", "negative_prompt": "x"}, "negative_prompt"),
        ({"model": "kling-2.5-turbo", "generate_audio": True}, "generate_audio"),
    ],
)
async def test_unsupported_combinations_fail_fast(tmp_path: Path, body, param):
    fake = FakeKling()

    (response,) = await run(tmp_path, fake, create({"prompt": "x", **body}))

    assert response.status_code == 400
    assert response.json()["error"]["param"] == param
    assert not any(r.method == "POST" for r in fake.requests)


@pytest.mark.parametrize(
    ("status", "code", "expected_status", "expected_code"),
    [
        (429, 1303, 429, "rate_limited"),
        (429, 1102, 402, "billing"),
        (400, 1301, 400, "content_policy"),
        (404, 1203, 404, "model_unavailable"),
    ],
)
async def test_kling_errors_map_to_unified_codes(
    tmp_path: Path, status, code, expected_status, expected_code
):
    fake = FakeKling()
    fake.create_response = (status, {"code": code, "message": "nope"})

    (response,) = await run(
        tmp_path, fake, create({"model": "kling-3.0", "prompt": "x"})
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


async def test_failed_tasks_carry_the_kling_message(tmp_path: Path):
    fake = FakeKling([legacy("failed", task_status_msg="Content risk detected")])

    _, failed = await run(
        tmp_path, fake, create({"model": "kling-3.0", "prompt": "x"}), follow()
    )

    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["message"] == "Content risk detected"
