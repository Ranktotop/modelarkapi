"""Google Veo 3.1 text-to-video on both backends (T9)."""

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

VERTEX_HOST = "us-central1-aiplatform.googleapis.com"
GEMINI_HOST = "generativelanguage.googleapis.com"
VIDEO_BYTES = b"\x00\x00\x00\x20ftypisomfake-video"


class FakeGoogle:
    """Records Google calls and plays back a scripted operation lifecycle."""

    def __init__(self, polls: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.polls = polls or []
        self.create_status = 200
        self.create_body: dict[str, Any] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if "/publishers/google/models/" in path and request.method == "GET":
            return httpx.Response(200, json={"name": path, "launchStage": "GA"})
        if request.url.host == GEMINI_HOST and path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/veo-3.1-fast-generate-preview",
                            "displayName": "Veo 3.1 fast",
                            "supportedGenerationMethods": ["predictLongRunning"],
                        },
                        {
                            "name": "models/gemini-omni-1.1-flash",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                    ]
                },
            )
        if path.endswith(":predictLongRunning"):
            if self.create_status != 200:
                return httpx.Response(self.create_status, json=self.create_body)
            model = path.rsplit("/", 1)[-1].split(":")[0]
            name = (
                f"models/{model}/operations/op-1"
                if request.url.host == GEMINI_HOST
                else f"projects/proj-1/locations/us-central1/publishers/google/models/{model}/operations/op-1"
            )
            return httpx.Response(200, json={"name": name})
        if path.endswith(":fetchPredictOperation") or "/operations/" in path:
            state = self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]
            return httpx.Response(200, json={"name": "op-1", **state})
        if path.endswith("/files/abc:download"):
            assert request.headers["x-goog-api-key"] == "gemini-key"
            return httpx.Response(
                200, content=VIDEO_BYTES, headers={"content-type": "video/mp4"}
            )
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}"}})

    def created(self) -> dict[str, Any]:
        return next(
            json.loads(r.content)
            for r in self.requests
            if r.url.path.endswith(":predictLongRunning")
        )


def vertex_done(count: int = 1) -> dict[str, Any]:
    return {
        "done": True,
        "response": {
            "@type": "type.googleapis.com/cloud.ai.large_models.vision.GenerateVideoResponse",
            "raiMediaFilteredCount": 0,
            "videos": [
                {
                    "bytesBase64Encoded": base64.b64encode(
                        VIDEO_BYTES + bytes([i])
                    ).decode(),
                    "mimeType": "video/mp4",
                }
                for i in range(count)
            ],
        },
    }


def settings_for(tmp_path: Path, backend: str) -> Settings:
    values: dict[str, Any] = {
        "proxy_api_key": None,
        "require_proxy_api_key": False,
        "media_dir": tmp_path / "media",
        "asset_job_db": tmp_path / "asset-jobs.db",
        "provider_job_db": tmp_path / "provider-jobs.db",
        "output_dir": tmp_path / "outputs",
        "google_veo_backend": backend,
        "google_omni_backend": "none",
        "provider_status_min_interval_seconds": 0,
    }
    if backend == "vertex":
        values["vertex_project"] = "proj-1"
    else:
        values["gemini_api_key"] = "gemini-key"
    return Settings(**values)


async def token() -> str:
    return "vertex-token"


async def run(settings: Settings, google: FakeGoogle, *calls):
    app = create_app(
        settings,
        google_transport=httpx.MockTransport(google),
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


async def test_vertex_models_are_listed_with_capabilities(tmp_path: Path):
    google = FakeGoogle()

    (models,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        lambda client, _: client.get("/v1/models"),
    )

    by_id = {model["id"]: model for model in models.json()["data"]}
    assert set(by_id) == {
        "veo-3.1-generate-001",
        "veo-3.1-fast-generate-001",
        "veo-3.1-lite-generate-001",
    }
    veo = by_id["veo-3.1-generate-001"]
    assert veo["owned_by"] == "google"
    assert veo["capabilities"]["provider"] == "google"
    assert veo["capabilities"]["backend"] == "vertex"
    assert veo["capabilities"]["parameters"]["seconds"]["values"] == [4, 6, 8]
    assert (
        "4k"
        not in by_id["veo-3.1-lite-generate-001"]["capabilities"]["parameters"][
            "resolution"
        ]["values"]
    )
    assert veo["links"]["prompt_guide"] == "/v1/prompt-guides/veo_3_1"


async def test_gemini_models_come_from_the_model_list(tmp_path: Path):
    (models,) = await run(
        settings_for(tmp_path, "gemini"),
        FakeGoogle(),
        lambda client, _: client.get("/v1/models"),
    )

    assert [model["id"] for model in models.json()["data"]] == [
        "veo-3.1-fast-generate-preview"
    ]
    assert (
        "negative_prompt" not in models.json()["data"][0]["capabilities"]["parameters"]
    )


async def test_vertex_text_to_video_end_to_end(tmp_path: Path):
    google = FakeGoogle(
        polls=[{"done": False, "metadata": {"progressPercent": 40}}, vertex_done()]
    )

    created, running, done, content = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create(
            {
                "model": "openai/veo-3.1-fast-generate-001",
                "prompt": "A paper boat on a pond",
                "seconds": 6,
                "size": "1280x720",
                "negative_prompt": "text",
                "generate_audio": False,
                "seed": 7,
            }
        ),
        follow(),
        follow(),
        follow("/content"),
    )

    assert created.status_code == 200
    assert created.json()["status"] == "queued"
    assert decode_video_id(created.json()["id"]).startswith("vid-veo-")
    assert google.created() == {
        "instances": [{"prompt": "A paper boat on a pond"}],
        "parameters": {
            "durationSeconds": 6,
            "resolution": "720p",
            "aspectRatio": "16:9",
            "negativePrompt": "text",
            "generateAudio": False,
            "seed": 7,
            "sampleCount": 1,
        },
    }
    create_request = next(
        r for r in google.requests if r.url.path.endswith(":predictLongRunning")
    )
    assert create_request.url.host == VERTEX_HOST
    assert create_request.url.path == (
        "/v1/projects/proj-1/locations/us-central1/publishers/google/models/"
        "veo-3.1-fast-generate-001:predictLongRunning"
    )
    assert create_request.headers["authorization"] == "Bearer vertex-token"
    assert running.json()["status"] == "in_progress"
    assert running.json()["progress"] == 40
    assert done.json()["status"] == "completed"
    assert done.json()["id"] == created.json()["id"]
    assert content.status_code == 200
    assert content.content == VIDEO_BYTES + b"\x00"
    assert content.headers["content-type"] == "video/mp4"


async def test_vertex_returns_multiple_outputs(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done(count=2)])

    _, done, second = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "fox", "n": 2}),
        follow(),
        follow("/content?output=1"),
    )

    assert google.created()["parameters"]["sampleCount"] == 2
    assert done.json()["status"] == "completed"
    assert second.content == VIDEO_BYTES + b"\x01"


async def test_gemini_text_to_video_downloads_with_the_api_key(tmp_path: Path):
    google = FakeGoogle(
        polls=[
            {
                "done": True,
                "response": {
                    "generateVideoResponse": {
                        "generatedSamples": [
                            {
                                "video": {
                                    "uri": f"https://{GEMINI_HOST}/v1beta/files/abc:download?alt=media"
                                }
                            }
                        ]
                    }
                },
            }
        ]
    )

    _, done, content = await run(
        settings_for(tmp_path, "gemini"),
        google,
        create(
            {"model": "veo-3.1-fast-generate-preview", "prompt": "fox", "seconds": 4}
        ),
        follow(),
        follow("/content"),
    )

    assert google.created() == {
        "instances": [{"prompt": "fox"}],
        "parameters": {
            "durationSeconds": 4,
            "resolution": "720p",
            "aspectRatio": "16:9",
            "sampleCount": 1,
        },
    }
    create_request = next(
        r for r in google.requests if r.url.path.endswith(":predictLongRunning")
    )
    assert create_request.headers["x-goog-api-key"] == "gemini-key"
    poll = next(r for r in google.requests if "/operations/" in r.url.path)
    assert (
        poll.url.path == "/v1beta/models/veo-3.1-fast-generate-preview/operations/op-1"
    )
    assert done.json()["status"] == "completed"
    assert content.content == VIDEO_BYTES


@pytest.mark.parametrize(
    ("body", "code", "param"),
    [
        ({"seconds": 5}, "unsupported_parameter", "seconds"),
        ({"resolution": "1080p", "seconds": 4}, "unsupported_parameter", "seconds"),
        ({"aspect_ratio": "1:1"}, "unsupported_parameter", "aspect_ratio"),
        ({"quality": "pro"}, "unsupported_parameter", "quality"),
        ({"task": "lip_sync"}, "unsupported_task", "task"),
        ({"n": 5}, "unsupported_parameter", "n"),
    ],
)
async def test_invalid_requests_fail_fast(tmp_path: Path, body, code, param):
    google = FakeGoogle()

    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-fast-generate-001", "prompt": "fox", **body}),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["param"] == param
    assert not any(r.url.path.endswith(":predictLongRunning") for r in google.requests)


async def test_gemini_rejects_vertex_only_parameters(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "gemini"),
        FakeGoogle(),
        create(
            {
                "model": "veo-3.1-fast-generate-preview",
                "prompt": "fox",
                "negative_prompt": "x",
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "negative_prompt"


async def test_filtered_generation_fails_with_content_policy(tmp_path: Path):
    google = FakeGoogle(
        polls=[
            {
                "done": True,
                "response": {
                    "raiMediaFilteredCount": 1,
                    "raiMediaFilteredReasons": ["Prompt blocked by safety filter"],
                    "videos": [],
                },
            }
        ]
    )

    _, failed, content = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "x"}),
        follow(),
        follow("/content"),
    )

    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["code"] == "content_policy"
    assert "safety filter" in failed.json()["error"]["message"]
    assert content.status_code == 409


async def test_operation_errors_fail_the_job(tmp_path: Path):
    google = FakeGoogle(
        polls=[{"done": True, "error": {"code": 3, "message": "Invalid duration"}}]
    )

    _, failed = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "x"}),
        follow(),
    )

    assert failed.json()["status"] == "failed"
    assert failed.json()["error"]["code"] == "upstream_error"
    assert failed.json()["error"]["message"] == "Invalid duration"


async def test_upstream_rate_limits_are_reported_as_retryable(tmp_path: Path):
    google = FakeGoogle()
    google.create_status = 429
    google.create_body = {
        "error": {
            "code": 429,
            "message": "Quota exceeded",
            "status": "RESOURCE_EXHAUSTED",
        }
    }

    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "x"}),
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


async def test_delete_removes_the_local_job(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    created, deleted, missing = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "x"}),
        lambda client, results: client.delete(f"/v1/videos/{results[0].json()['id']}"),
        follow(),
    )

    assert deleted.status_code == 200
    assert missing.status_code == 404


async def test_native_route_passes_the_veo_body_through(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])
    native_body = {
        "instances": [{"prompt": "fox"}],
        "parameters": {"durationSeconds": 8, "compressionQuality": "lossless"},
    }

    created, status = await run(
        settings_for(tmp_path, "vertex"),
        google,
        lambda client, _: client.post(
            "/v1/providers/google/veo/veo-3.1-generate-001:predictLongRunning",
            json=native_body,
        ),
        lambda client, results: client.get(results[0].json()["proxy"]["status_url"]),
    )

    assert google.created() == native_body
    assert created.json()["name"].endswith("/operations/op-1")
    assert status.json()["status"] == "completed"


# --- T10: image modes -------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()


def image(role: str | None = None) -> dict[str, Any]:
    reference = {"type": "image", "url": PNG_URI}
    return {**reference, "role": role} if role else reference


async def test_vertex_image_to_video_embeds_the_first_frame(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-fast-generate-001", "references": [image()]}),
    )

    assert created.status_code == 200
    body = google.created()
    assert body["instances"] == [
        {
            "prompt": "",
            "image": {"bytesBase64Encoded": PNG_B64, "mimeType": "image/png"},
        }
    ]


async def test_first_and_last_frame_force_eight_seconds(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    created, rejected = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create(
            {
                "model": "veo-3.1-generate-001",
                "prompt": "morph",
                "references": [image("first_frame"), image("last_frame")],
            }
        ),
        create(
            {
                "model": "veo-3.1-generate-001",
                "prompt": "morph",
                "seconds": 4,
                "references": [image("first_frame"), image("last_frame")],
            }
        ),
    )

    instance = google.created()["instances"][0]
    assert set(instance) == {"prompt", "image", "lastFrame"}
    assert google.created()["parameters"]["durationSeconds"] == 8
    assert created.status_code == 200
    assert rejected.status_code == 400


async def test_reference_images_become_asset_references(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create(
            {
                "model": "veo-3.1-generate-001",
                "prompt": "the cat",
                "references": [image(), image()],
            }
        ),
    )

    assert created.status_code == 200
    body = google.created()
    assert (
        body["instances"][0]["referenceImages"]
        == [
            {
                "image": {"bytesBase64Encoded": PNG_B64, "mimeType": "image/png"},
                "referenceType": "asset",
            }
        ]
        * 2
    )
    assert body["parameters"]["durationSeconds"] == 8


async def test_lite_has_no_reference_images(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        FakeGoogle(),
        create(
            {
                "model": "veo-3.1-lite-generate-001",
                "prompt": "x",
                "references": [image(), image()],
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_task"


async def test_veo_accepts_only_image_references(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "vertex"),
        FakeGoogle(),
        create(
            {
                "model": "veo-3.1-generate-001",
                "prompt": "x",
                "references": [
                    image(),
                    {"type": "audio", "url": "https://e.example/a.mp3"},
                ],
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reference_limit"


async def test_gemini_image_modes_send_allow_adult(tmp_path: Path):
    google = FakeGoogle(polls=[{"done": False}])

    (created,) = await run(
        settings_for(tmp_path, "gemini"),
        google,
        create({"model": "veo-3.1-fast-generate-preview", "references": [image()]}),
    )

    assert created.status_code == 200
    assert google.created()["parameters"]["personGeneration"] == "allow_adult"


# --- T11: extension -----------------------------------------------------------

MP4_URI = "data:video/mp4;base64," + base64.b64encode(VIDEO_BYTES).decode()


async def test_vertex_extends_an_earlier_job_without_a_duration(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    first, _, extension = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create({"model": "veo-3.1-generate-001", "prompt": "a boat"}),
        follow(),
        lambda client, results: client.post(
            "/v1/videos",
            json={
                "model": "veo-3.1-generate-001",
                "task": "extend",
                "prompt": "the boat sails on",
                "references": [
                    {"task_id": results[0].json()["id"], "role": "base_video"}
                ],
            },
        ),
    )

    assert extension.status_code == 200
    body = [
        json.loads(r.content)
        for r in google.requests
        if r.url.path.endswith(":predictLongRunning")
    ][1]
    assert body["instances"][0]["video"] == {
        "bytesBase64Encoded": base64.b64encode(VIDEO_BYTES + b"\x00").decode(),
        "mimeType": "video/mp4",
    }
    assert "durationSeconds" not in body["parameters"]


async def test_vertex_extends_uploaded_videos(tmp_path: Path):
    google = FakeGoogle(polls=[vertex_done()])

    (created,) = await run(
        settings_for(tmp_path, "vertex"),
        google,
        create(
            {
                "model": "veo-3.1-lite-generate-001",
                "task": "extend",
                "prompt": "continue",
                "references": [{"type": "video", "url": MP4_URI}],
            }
        ),
    )

    assert created.status_code == 200
    assert google.created()["instances"][0]["video"]["mimeType"] == "video/mp4"


def gemini_done() -> dict[str, Any]:
    return {
        "done": True,
        "response": {
            "generateVideoResponse": {
                "generatedSamples": [
                    {
                        "video": {
                            "uri": f"https://{GEMINI_HOST}/v1beta/files/abc:download?alt=media"
                        }
                    }
                ]
            }
        },
    }


async def test_gemini_extends_its_own_videos_inline(tmp_path: Path):
    google = FakeGoogle(polls=[gemini_done()])

    _, _, extension, too_sharp = await run(
        settings_for(tmp_path, "gemini"),
        google,
        create({"model": "veo-3.1-fast-generate-preview", "prompt": "a boat"}),
        follow(),
        lambda client, results: client.post(
            "/v1/videos",
            json={
                "model": "veo-3.1-fast-generate-preview",
                "task": "extend",
                "prompt": "on and on",
                "references": [{"task_id": results[0].json()["id"]}],
            },
        ),
        lambda client, results: client.post(
            "/v1/videos",
            json={
                "model": "veo-3.1-fast-generate-preview",
                "task": "extend",
                "resolution": "1080p",
                "references": [{"task_id": results[0].json()["id"]}],
            },
        ),
    )

    assert extension.status_code == 200
    body = [
        json.loads(r.content)
        for r in google.requests
        if r.url.path.endswith(":predictLongRunning")
    ][1]
    assert body["instances"][0]["video"] == {
        "inlineData": {
            "mimeType": "video/mp4",
            "data": base64.b64encode(VIDEO_BYTES).decode(),
        }
    }
    assert body["parameters"]["durationSeconds"] == 8
    assert body["parameters"]["resolution"] == "720p"
    assert too_sharp.status_code == 400


async def test_gemini_cannot_extend_foreign_videos(tmp_path: Path):
    (response,) = await run(
        settings_for(tmp_path, "gemini"),
        FakeGoogle(),
        create(
            {
                "model": "veo-3.1-fast-generate-preview",
                "task": "extend",
                "references": [{"type": "video", "url": MP4_URI}],
            }
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "reference_limit"


async def test_veo_models_advertise_video_extension(tmp_path: Path):
    (models,) = await run(
        settings_for(tmp_path, "vertex"),
        FakeGoogle(),
        lambda client, _: client.get("/v1/models"),
    )

    caps = models.json()["data"][0]["capabilities"]
    assert caps["continuation"] == "video_extension"
    assert caps["tasks"]["extend"]["references"][0]["role"] == "base_video"


async def test_default_parameter_policy_can_be_adapt(tmp_path: Path):
    google = FakeGoogle(polls=[{"done": False}])
    settings = settings_for(tmp_path, "vertex")
    settings.default_parameter_policy = "adapt"

    (response,) = await run(
        settings,
        google,
        create({"model": "veo-3.1-fast-generate-001", "prompt": "fox", "seconds": 5}),
    )

    assert response.status_code == 200, response.text
    sent = next(
        r for r in google.requests if r.url.path.endswith(":predictLongRunning")
    )
    assert json.loads(sent.content)["parameters"]["durationSeconds"] in {4, 6}
