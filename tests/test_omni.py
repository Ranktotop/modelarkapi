"""Gemini Omni Flash through the Interactions API (T12)."""

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

VERTEX_HOST = "aiplatform.googleapis.com"
GEMINI_HOST = "generativelanguage.googleapis.com"
VIDEO = b"\x00\x00\x00\x20ftypisomomni-video"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()
FILE_URI = f"https://{GEMINI_HOST}/v1beta/files/f1:download?alt=media"


def completed(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "v1_abc",
        "status": "completed",
        "usage": {
            "total_output_tokens": 6155,
            "output_tokens_by_modality": [{"modality": "video", "tokens": 5793}],
        },
        "steps": [
            {"type": "user_input", "content": [{"type": "text", "text": "x"}]},
            {
                "type": "model_output",
                "content": [{"type": "video", "mime_type": "video/mp4", **content}],
            },
        ],
    }


class FakeOmni:
    def __init__(self, states: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.states = states or [{"id": "v1_abc", "status": "in_progress"}]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if "/publishers/google/models/" in path:
            return httpx.Response(200, json={"name": path})
        if request.url.host == GEMINI_HOST and path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-omni-1.1-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/gemini-2.5-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                    ]
                },
            )
        if path.endswith("/interactions") and request.method == "POST":
            return httpx.Response(
                200,
                json={"id": "v1_abc", "status": "in_progress", "object": "interaction"},
            )
        if path.endswith("/interactions/v1_abc/cancel"):
            return httpx.Response(200, json={"id": "v1_abc", "status": "cancelled"})
        if path.endswith("/interactions/v1_abc"):
            state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return httpx.Response(200, json=state)
        if path.endswith("/files/f1:download"):
            assert request.headers["x-goog-api-key"] == "gemini-key"
            return httpx.Response(
                200, content=VIDEO, headers={"content-type": "video/mp4"}
            )
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}"}})

    def created(self) -> dict[str, Any]:
        return next(
            json.loads(r.content)
            for r in self.requests
            if r.url.path.endswith("/interactions") and r.method == "POST"
        )


def settings_for(tmp_path: Path, backend: str) -> Settings:
    values: dict[str, Any] = {
        "proxy_api_key": None,
        "require_proxy_api_key": False,
        "media_dir": tmp_path / "media",
        "asset_job_db": tmp_path / "asset-jobs.db",
        "provider_job_db": tmp_path / "provider-jobs.db",
        "output_dir": tmp_path / "outputs",
        "google_omni_backend": backend,
        "google_veo_backend": "none",
        "provider_status_min_interval_seconds": 0,
    }
    if backend == "vertex":
        values["vertex_project"] = "proj-1"
    else:
        values["gemini_api_key"] = "gemini-key"
    return Settings(**values)


async def token() -> str:
    return "vertex-token"


async def run(settings: Settings, fake: FakeOmni, *calls):
    app = create_app(
        settings,
        google_transport=httpx.MockTransport(fake),
        vertex_token_source=token,
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


async def test_vertex_lists_the_omni_preview_models(tmp_path: Path):
    (models,) = await run(
        settings_for(tmp_path, "vertex"), FakeOmni(), lambda c, _: c.get("/v1/models")
    )

    by_id = {m["id"]: m for m in models.json()["data"]}
    assert set(by_id) == {"gemini-omni-1.1-flash-preview", "gemini-omni-flash-preview"}
    full = by_id["gemini-omni-1.1-flash-preview"]["capabilities"]
    assert full["backend"] == "vertex"
    assert full["parameters"]["seconds"]["values"] == list(range(3, 11))
    assert set(full["tasks"]) >= {"text_to_video", "image_to_video", "first_last_frame"}
    limited = by_id["gemini-omni-flash-preview"]["capabilities"]
    assert limited["parameters"]["resolution"]["values"] == ["720p"]
    assert "image_to_video" not in limited["tasks"]


async def test_gemini_lists_the_ga_model(tmp_path: Path):
    (models,) = await run(
        settings_for(tmp_path, "gemini"), FakeOmni(), lambda c, _: c.get("/v1/models")
    )

    assert [m["id"] for m in models.json()["data"]] == ["gemini-omni-1.1-flash"]


async def test_vertex_text_to_video_runs_in_the_background(tmp_path: Path):
    fake = FakeOmni(
        [
            {"id": "v1_abc", "status": "in_progress"},
            completed({"data": base64.b64encode(VIDEO).decode()}),
        ]
    )

    created, running, done, content = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "prompt": "a red boat",
                "seconds": 5,
                "size": "720x1280",
            }
        ),
        follow(),
        follow(),
        follow("/content"),
    )

    assert created.status_code == 200
    assert decode_video_id(created.json()["id"]).startswith("vid-omni-")
    post = next(r for r in fake.requests if r.method == "POST")
    assert post.url.host == VERTEX_HOST
    assert post.url.path == "/v1beta1/projects/proj-1/locations/global/interactions"
    assert fake.created() == {
        "model": "gemini-omni-1.1-flash-preview",
        "input": "a red boat",
        "response_format": {
            "type": "video",
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "5s",
        },
        "background": True,
        "store": True,
    }
    assert running.json()["status"] == "in_progress"
    assert done.json()["status"] == "completed"
    assert done.json()["usage"]["output_tokens"] == 6155
    assert content.content == VIDEO


async def test_gemini_delivers_through_the_files_api(tmp_path: Path):
    fake = FakeOmni([completed({"uri": FILE_URI})])

    _, done, content = await run(
        settings_for(tmp_path, "gemini"),
        fake,
        create({"model": "gemini-omni-1.1-flash", "prompt": "fox"}),
        follow(),
        follow("/content"),
    )

    assert fake.created()["response_format"]["delivery"] == "uri"
    post = next(r for r in fake.requests if r.method == "POST")
    assert post.url.path == "/v1beta/interactions"
    assert post.headers["x-goog-api-key"] == "gemini-key"
    assert done.json()["status"] == "completed"
    assert content.content == VIDEO


async def test_image_to_video_sends_the_image_before_the_prompt(tmp_path: Path):
    fake = FakeOmni()

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "prompt": "wake up",
                "references": [{"type": "image", "url": PNG_URI}],
            }
        ),
    )

    assert created.status_code == 200
    body = fake.created()
    assert body["input"] == [
        {"type": "image", "mime_type": "image/png", "data": PNG_B64},
        {"type": "text", "text": "wake up"},
    ]
    assert body["generation_config"] == {"video_config": {"task": "image_to_video"}}


async def test_first_and_last_frame_keep_their_order(tmp_path: Path):
    fake = FakeOmni()
    first = {"type": "image", "url": PNG_URI, "role": "first_frame"}
    last = {
        "type": "image",
        "url": "data:image/jpeg;base64,"
        + base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 20).decode(),
        "role": "last_frame",
    }

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "prompt": "morph",
                "references": [last, first],
            }
        ),
    )

    assert created.status_code == 200
    mime_types = [part.get("mime_type") for part in fake.created()["input"]]
    assert mime_types == ["image/png", "image/jpeg", None]


@pytest.mark.parametrize(
    ("model", "body", "code"),
    [
        ("gemini-omni-1.1-flash-preview", {"seconds": 12}, "unsupported_parameter"),
        (
            "gemini-omni-1.1-flash-preview",
            {"generate_audio": False},
            "unsupported_parameter",
        ),
        (
            "gemini-omni-1.1-flash-preview",
            {"negative_prompt": "blur"},
            "unsupported_parameter",
        ),
        ("gemini-omni-flash-preview", {"resolution": "1080p"}, "unsupported_parameter"),
        (
            "gemini-omni-flash-preview",
            {"references": [{"type": "image", "url": PNG_URI}]},
            "unsupported_task",
        ),
    ],
)
async def test_invalid_omni_requests_fail_fast(tmp_path: Path, model, body, code):
    fake = FakeOmni()

    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": model, "prompt": "x", **body}),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert not any(r.method == "POST" for r in fake.requests)


async def test_failed_interactions_fail_the_job(tmp_path: Path):
    fake = FakeOmni(
        [{"id": "v1_abc", "status": "failed", "error": {"message": "Unsafe content"}}]
    )

    _, failed = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "x"}),
        follow(),
    )

    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["message"] == "Unsafe content"


async def test_deleting_a_running_job_cancels_it_upstream(tmp_path: Path):
    fake = FakeOmni()

    _, deleted = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "x"}),
        lambda c, results: c.delete(f"/v1/videos/{results[0].json()['id']}"),
    )

    assert deleted.status_code == 200
    assert deleted.json()["object"] == "video.deleted"
    assert any(
        r.url.path.endswith("/interactions/v1_abc/cancel") for r in fake.requests
    )


# --- T13: references, edit, extend, multi-turn --------------------------------

MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 24
MP4_URI = "data:video/mp4;base64," + base64.b64encode(MP4).decode()
MP4_B64 = base64.b64encode(MP4).decode()


def done_vertex():
    return completed({"data": base64.b64encode(VIDEO).decode()})


async def test_reference_images_and_videos_become_input_parts(tmp_path: Path):
    fake = FakeOmni()

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "task": "reference_to_video",
                "prompt": "<IMAGE_REF_0> dances like <VIDEO_REF_0>",
                "references": [
                    {"type": "image", "url": PNG_URI},
                    {"type": "video", "url": MP4_URI},
                ],
            }
        ),
    )

    assert created.status_code == 200
    body = fake.created()
    assert body["input"] == [
        {"type": "image", "mime_type": "image/png", "data": PNG_B64},
        {"type": "video", "mime_type": "video/mp4", "data": MP4_B64},
        {"type": "text", "text": "<IMAGE_REF_0> dances like <VIDEO_REF_0>"},
    ]
    assert body["generation_config"] == {"video_config": {"task": "reference_to_video"}}


async def test_at_most_three_reference_videos(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        FakeOmni(),
        create(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "task": "reference_to_video",
                "prompt": "x",
                "references": [{"type": "video", "url": MP4_URI}] * 4,
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reference_limit"


async def test_uploaded_videos_are_edited_inline(tmp_path: Path):
    fake = FakeOmni()

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create(
            {
                "model": "gemini-omni-flash-preview",
                "task": "edit",
                "prompt": "make it night",
                "references": [{"type": "video", "url": MP4_URI}],
            }
        ),
    )

    assert created.status_code == 200
    body = fake.created()
    assert body["input"][0] == {
        "type": "video",
        "mime_type": "video/mp4",
        "data": MP4_B64,
    }
    assert body["generation_config"] == {"video_config": {"task": "edit"}}
    assert "previous_interaction_id" not in body


async def test_extending_an_own_job_continues_the_interaction(tmp_path: Path):
    fake = FakeOmni([done_vertex()])

    _, _, extension = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "a boat"}),
        follow(),
        lambda c, results: c.post(
            "/v1/videos",
            json={
                "model": "gemini-omni-1.1-flash-preview",
                "task": "extend",
                "prompt": "it sails away",
                "seconds": 4,
                "references": [{"task_id": results[0].json()["id"]}],
            },
        ),
    )

    assert extension.status_code == 200
    body = [
        json.loads(r.content)
        for r in fake.requests
        if r.method == "POST" and r.url.path.endswith("/interactions")
    ][1]
    assert body["previous_interaction_id"] == "v1_abc"
    assert body["input"] == [{"type": "text", "text": "it sails away"}]
    assert body["generation_config"] == {"video_config": {"task": "extend"}}
    assert body["response_format"]["duration"] == "4s"


async def test_remix_edits_the_source_video_with_extra_body_fields(tmp_path: Path):
    fake = FakeOmni([done_vertex()])

    created, _, remix = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "a boat"}),
        follow(),
        lambda c, results: c.post(
            f"/v1/videos/{results[0].json()['id']}/remix",
            json={"prompt": "make it snow", "resolution": "1080p"},
        ),
    )

    assert remix.status_code == 200
    assert remix.json()["remixed_from_video_id"] == created.json()["id"]
    assert decode_video_id(remix.json()["id"]).startswith("vid-omni-")
    body = [
        json.loads(r.content)
        for r in fake.requests
        if r.method == "POST" and r.url.path.endswith("/interactions")
    ][1]
    assert body["previous_interaction_id"] == "v1_abc"
    assert body["generation_config"] == {"video_config": {"task": "edit"}}
    assert body["response_format"]["resolution"] == "1080p"


async def test_edits_and_extensions_routes_follow_the_openai_shape(tmp_path: Path):
    fake = FakeOmni([done_vertex()])

    created, _, edit, extension = await run(
        settings_for(tmp_path, "vertex"),
        fake,
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "a boat"}),
        follow(),
        lambda c, results: c.post(
            "/v1/videos/edits",
            json={"prompt": "paint it red", "video": {"id": results[0].json()["id"]}},
        ),
        lambda c, results: c.post(
            "/v1/videos/extensions",
            json={
                "prompt": "keep going",
                "seconds": "6",
                "video": {"id": results[0].json()["id"]},
            },
        ),
    )

    assert edit.status_code == 200
    assert extension.status_code == 200
    bodies = [
        json.loads(r.content)
        for r in fake.requests
        if r.method == "POST" and r.url.path.endswith("/interactions")
    ]
    assert [b["generation_config"]["video_config"]["task"] for b in bodies[1:]] == [
        "edit",
        "extend",
    ]
    assert bodies[2]["response_format"]["duration"] == "6s"


async def test_the_first_omni_preview_cannot_extend(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        FakeOmni(),
        create(
            {
                "model": "gemini-omni-flash-preview",
                "task": "extend",
                "prompt": "x",
                "references": [{"type": "video", "url": MP4_URI}],
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_task"


async def test_omni_continues_by_multi_turn(tmp_path: Path):
    (models,) = await run(
        settings_for(tmp_path, "vertex"), FakeOmni(), lambda c, _: c.get("/v1/models")
    )

    caps = {m["id"]: m["capabilities"] for m in models.json()["data"]}
    assert caps["gemini-omni-1.1-flash-preview"]["continuation"] == "multi_turn"
    assert set(caps["gemini-omni-1.1-flash-preview"]["tasks"]) >= {
        "reference_to_video",
        "edit",
        "extend",
    }
    assert set(caps["gemini-omni-flash-preview"]["tasks"]) == {"text_to_video", "edit"}


async def test_both_backends_route_ga_to_gemini_and_previews_to_vertex(tmp_path: Path):
    fake = FakeOmni()
    settings = settings_for(tmp_path, "both")
    settings.vertex_project = "proj-1"

    models, ga, preview, ga_status = await run(
        settings,
        fake,
        lambda c, _: c.get("/v1/models"),
        create({"model": "gemini-omni-1.1-flash", "prompt": "x"}),
        create({"model": "gemini-omni-1.1-flash-preview", "prompt": "x"}),
        lambda c, results: c.get(f"/v1/videos/{results[1].json()['id']}"),
    )

    listed = {m["id"]: m["capabilities"]["backend"] for m in models.json()["data"]}
    assert listed["gemini-omni-1.1-flash"] == "gemini"
    assert listed["gemini-omni-1.1-flash-preview"] == "vertex"
    assert (ga.status_code, preview.status_code) == (200, 200)
    hosts = [
        r.url.host
        for r in fake.requests
        if r.url.path.endswith("/interactions") and r.method == "POST"
    ]
    assert hosts == [GEMINI_HOST, VERTEX_HOST]
    assert ga_status.status_code == 200
    polls = [
        r.url.host for r in fake.requests if r.url.path.endswith("/interactions/v1_abc")
    ]
    assert polls[-1] == GEMINI_HOST
