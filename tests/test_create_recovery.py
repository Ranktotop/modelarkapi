"""Creates that time out: generous timeouts and recovering the provider ID.

A create is never sent twice (that could bill twice). After a timeout the
proxy looks the task up where the provider allows it; otherwise it fails.
See tasks/research/create-recovery.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_video_id

SEEDANCE = "dreamina-seedance-2-5-260628"


def settings_for(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
        create_recovery_seconds=0.3,
        create_recovery_interval_seconds=0.05,
        **extra,
    )


async def post(app, body: dict[str, Any]) -> tuple[httpx.Response, dict | None]:
    """The response and, if one was created, the registered job."""
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post("/v1/videos", json=body)
        job = None
        if response.status_code == 200:
            job = app.state.provider_jobs.get(decode_video_id(response.json()["id"]))
        return response, job


def posts(requests: list[httpx.Request]) -> list[httpx.Request]:
    return [r for r in requests if r.method == "POST"]


# --- generous timeouts ---------------------------------------------------------


async def test_creates_use_the_long_create_timeout(tmp_path: Path):
    seen: dict[str, float] = {}

    def ark(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["seedance"] = request.extensions["timeout"]["read"]
            return httpx.Response(200, json={"id": "cgt-1"})
        return httpx.Response(200, json={"items": []})

    def kling(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["kling"] = request.extensions["timeout"]["read"]
        data = {"task_id": "t1", "task_status": "submitted"}
        return httpx.Response(200, json={"code": 0, "data": data})

    settings = settings_for(tmp_path, ark_api_key="ark", kling_api_key="kling-key")
    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(ark),
        kling_transport=httpx.MockTransport(kling),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        await client.post("/v1/videos", json={"model": SEEDANCE, "prompt": "fox"})
        await client.post(
            "/v1/videos", json={"model": "kling-2.5-turbo", "prompt": "fox"}
        )

    assert seen == {
        "seedance": settings.create_timeout_seconds,
        "kling": settings.create_timeout_seconds,
    }
    assert settings.create_timeout_seconds >= 600


# --- Kling: our external_task_id finds the task ---------------------------------


class KlingTimeout:
    """Create times out; the task exists upstream under our external ID."""

    def __init__(self, found: bool = True) -> None:
        self.requests: list[httpx.Request] = []
        self.external: str | None = None
        self.found = found

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        ok = lambda data: httpx.Response(200, json={"code": 0, "data": data})
        if request.method == "POST":
            body = json.loads(request.content)
            self.external = body.get("external_task_id") or (
                body.get("options") or {}
            ).get("external_task_id")
            raise httpx.ReadTimeout("slow", request=request)
        if not self.found:
            return httpx.Response(404, json={"code": 1201, "message": "not found"})
        if request.url.path == "/tasks":
            assert request.url.params["external_task_ids"] == self.external
            return ok(
                [{"id": "n-1", "external_id": self.external, "status": "submitted"}]
            )
        assert request.url.path.endswith(f"/{self.external}")
        return ok({"task_id": "t-1", "task_status": "submitted"})


@pytest.mark.parametrize(
    ("model", "task_id"), [("kling-2.5-turbo", "t-1"), ("kling-3.0-turbo", "n-1")]
)
async def test_kling_recovers_a_timed_out_create(tmp_path: Path, model, task_id):
    fake = KlingTimeout()
    app = create_app(
        settings_for(tmp_path, kling_api_key="kling-key"),
        kling_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )

    response, job = await post(app, {"model": model, "prompt": "fox", "seconds": 5})

    assert response.status_code == 200, response.text
    assert fake.external and fake.external.startswith("vid-kling-")
    assert len(posts(fake.requests)) == 1
    assert job["upstream"]["task_id"] == task_id


async def test_kling_fails_when_the_task_cannot_be_found(tmp_path: Path):
    fake = KlingTimeout(found=False)
    app = create_app(
        settings_for(tmp_path, kling_api_key="kling-key"),
        kling_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )

    response, _ = await post(app, {"model": "kling-2.5-turbo", "prompt": "fox"})

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "upstream_timeout"
    assert len(posts(fake.requests)) == 1


# --- Seedance: match the task list ---------------------------------------------


def seedance_list(*tasks: dict[str, Any]):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"items": list(tasks), "total": len(tasks)})

    return handler, requests


def task(task_id: str, created: int, **fields: Any) -> dict[str, Any]:
    return {
        "id": task_id,
        "model": SEEDANCE,
        "status": "running",
        "created_at": created,
        "resolution": "480p",
        "ratio": "16:9",
        "duration": 4,
        **fields,
    }


async def test_seedance_adopts_the_single_matching_task(tmp_path: Path):
    now = int(time.time())
    handler, requests = seedance_list(
        task("cgt-old", now - 3600),
        task("cgt-other", now, resolution="1080p"),
        task("cgt-mine", now),
    )
    app = create_app(
        settings_for(tmp_path, ark_api_key="ark"),
        ark_transport=httpx.MockTransport(handler),
        validate_startup_credentials=False,
    )

    response, _ = await post(
        app,
        {
            "model": SEEDANCE,
            "prompt": "fox",
            "seconds": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
        },
    )

    assert response.status_code == 200, response.text
    assert decode_video_id(response.json()["id"]) == "cgt-mine"
    assert len(posts(requests)) == 1


async def test_seedance_fails_on_an_ambiguous_match(tmp_path: Path):
    now = int(time.time())
    handler, requests = seedance_list(task("cgt-a", now), task("cgt-b", now))
    app = create_app(
        settings_for(tmp_path, ark_api_key="ark"),
        ark_transport=httpx.MockTransport(handler),
        validate_startup_credentials=False,
    )

    response, _ = await post(
        app,
        {
            "model": SEEDANCE,
            "prompt": "fox",
            "seconds": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
        },
    )

    assert response.status_code == 504
    assert len(posts(requests)) == 1


# --- Omni: the stream names the interaction before rendering --------------------


class SlowStream(httpx.AsyncByteStream):
    """Sends interaction.created, then stalls like a long render."""

    async def __aiter__(self):
        created = {
            "event_type": "interaction.created",
            "interaction": {"id": "v1_streamed", "status": "in_progress"},
        }
        yield b"event: interaction.created\n"
        yield f"data: {json.dumps(created)}\n\n".encode()
        raise httpx.ReadTimeout("render takes a while")


async def test_omni_takes_the_id_from_the_stream(tmp_path: Path):
    requests: list[httpx.Request] = []

    def google(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "/publishers/google/models/" in request.url.path:
            return httpx.Response(200, json={"name": request.url.path})
        if request.method == "POST":
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=SlowStream()
            )
        return httpx.Response(200, json={"id": "v1_streamed", "status": "in_progress"})

    async def token() -> str:
        return "vertex-token"

    app = create_app(
        settings_for(
            tmp_path,
            vertex_project="proj-1",
            google_omni_backend="vertex",
            google_veo_backend="none",
        ),
        google_transport=httpx.MockTransport(google),
        vertex_token_source=token,
        validate_startup_credentials=False,
    )

    response, job = await post(
        app, {"model": "gemini-omni-1.1-flash-preview", "prompt": "x"}
    )

    assert response.status_code == 200, response.text
    sent = json.loads(posts(requests)[0].content)
    assert sent["stream"] is True and sent["background"] is True
    assert job["upstream"]["interaction"] == "v1_streamed"
