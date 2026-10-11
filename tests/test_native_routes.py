"""Native ModelArk task and Google interaction routes (docs/SPEC.md 16.2, 16.3)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

MODEL = "dreamina-seedance-2-5-260628"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 32
GEMINI_HOST = "generativelanguage.googleapis.com"


def settings_for(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
        **extra,
    )


class Recorder:
    def __init__(self, handler) -> None:
        self.requests: list[httpx.Request] = []
        self.handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    def posted(self) -> dict[str, Any]:
        return json.loads(next(r for r in self.requests if r.method == "POST").content)


def modelark(request: httpx.Request) -> httpx.Response:
    if request.method == "POST":
        return httpx.Response(200, json={"id": "cgt-native"})
    if request.method == "DELETE":
        return httpx.Response(200, json={})
    if request.url.path.endswith("/tasks"):
        return httpx.Response(200, json={"items": [{"id": "cgt-native"}], "total": 1})
    return httpx.Response(
        200, json={"id": "cgt-native", "model": MODEL, "status": "running"}
    )


async def run(app, *calls):
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


async def test_native_modelark_tasks(tmp_path: Path):
    ark = Recorder(modelark)
    app = create_app(
        settings_for(tmp_path, ark_api_key="ark-test"),
        ark_transport=httpx.MockTransport(ark),
        validate_startup_credentials=False,
    )

    upload, created, status, listed, unified, deleted = await run(
        app,
        lambda c, _: c.post(
            "/v1/media/references", files={"file": ("clip.mp4", MP4, "video/mp4")}
        ),
        lambda c, r: c.post(
            "/v1/providers/modelark/tasks",
            json={
                "model": MODEL,
                "content": [
                    {"type": "text", "text": "fox"},
                    {
                        "type": "image_url",
                        "image_url": {"url": PNG_URI},
                        "role": "reference_image",
                    },
                    {
                        "type": "video_url",
                        "video_url": {"url": r[0].json()["data"][0]["id"]},
                        "role": "reference_video",
                    },
                ],
                "omni_reference_task_type": "reference",
            },
        ),
        lambda c, _: c.get("/v1/providers/modelark/tasks/cgt-native"),
        lambda c, _: c.get("/v1/providers/modelark/tasks?page_size=5"),
        lambda c, r: c.get(r[1].json()["proxy"]["status_url"]),
        lambda c, _: c.delete("/v1/providers/modelark/tasks/cgt-native"),
    )

    assert upload.status_code == 200, upload.text
    assert created.status_code == 200, created.text
    assert created.json()["id"] == "cgt-native"
    assert created.json()["proxy"]["id"].startswith("video_")
    content = ark.posted()["content"]
    assert content[1]["image_url"]["url"] == PNG_URI
    assert content[2]["video_url"]["url"] == upload.json()["data"][0]["url"]
    assert ark.posted()["omni_reference_task_type"] == "reference"
    assert status.json() == {"id": "cgt-native", "model": MODEL, "status": "running"}
    assert listed.json()["total"] == 1
    assert unified.json()["status"] == "in_progress"
    assert deleted.status_code == 200
    assert any(r.method == "DELETE" for r in ark.requests)


def omni(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/models"):
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-omni-1.1-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        )
    if path.endswith("/interactions"):
        return httpx.Response(200, json={"id": "v1_native", "status": "in_progress"})
    if path.endswith("/cancel"):
        return httpx.Response(200, json={"id": "v1_native", "status": "cancelled"})
    return httpx.Response(200, json={"id": "v1_native", "status": "in_progress"})


async def test_native_google_interactions(tmp_path: Path):
    google = Recorder(omni)
    app = create_app(
        settings_for(
            tmp_path,
            gemini_api_key="gemini-key",
            google_omni_backend="gemini",
            google_veo_backend="none",
        ),
        google_transport=httpx.MockTransport(google),
        validate_startup_credentials=False,
    )

    created, status, cancelled, deleted, gone = await run(
        app,
        lambda c, _: c.post(
            "/v1/providers/google/interactions",
            json={
                "model": "gemini-omni-1.1-flash",
                "input": [{"type": "text", "text": "a fox"}],
                "background": False,
            },
        ),
        lambda c, r: c.get(
            f"/v1/providers/google/interactions/{r[0].json()['proxy']['id']}"
        ),
        lambda c, r: c.post(
            f"/v1/providers/google/interactions/{r[0].json()['proxy']['id']}/cancel"
        ),
        lambda c, r: c.delete(
            f"/v1/providers/google/interactions/{r[0].json()['proxy']['id']}"
        ),
        lambda c, r: c.get(r[0].json()["proxy"]["status_url"]),
    )

    assert created.status_code == 200, created.text
    assert created.json()["id"] == "v1_native"
    sent = json.loads(
        next(r for r in google.requests if r.url.path.endswith("/interactions")).content
    )
    assert sent["background"] is True
    assert sent["store"] is True
    assert sent["input"] == [{"type": "text", "text": "a fox"}]
    assert status.json()["id"] == "v1_native"
    assert cancelled.json()["status"] == "cancelled"
    assert deleted.status_code == 200
    assert gone.status_code == 404
