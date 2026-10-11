"""Kling text-to-speech, text-to-audio and video-to-audio (T19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

CDN = "v1-kling.klingai.com"
MP3 = b"ID3\x03\x00\x00\x00kling-mp3"
WAV = b"RIFF\x00\x00\x00\x00WAVEkling-wav"
VIDEO = b"\x00\x00\x00\x20ftypisomwith-sound"


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        ok = lambda data: httpx.Response(200, json={"code": 0, "data": data})  # noqa: E731
        if request.url.host == CDN:
            content = {"/a.mp3": MP3, "/a.wav": WAV, "/v.mp4": VIDEO}[path]
            return httpx.Response(200, content=content)
        if path == "/v1/audio/tts":
            return ok(
                {
                    "task_id": "A",
                    "task_status": "succeed",
                    "task_result": {
                        "audios": [
                            {
                                "id": "aud-1",
                                "url": f"https://{CDN}/a.mp3",
                                "duration": "2.1",
                            }
                        ]
                    },
                }
            )
        if request.method == "POST":
            return ok({"task_id": "T1", "task_status": "submitted"})
        result: dict[str, Any] = {
            "audios": [
                {
                    "id": "au",
                    "url_mp3": f"https://{CDN}/a.mp3",
                    "url_wav": f"https://{CDN}/a.wav",
                    "duration_mp3": "4.5",
                }
            ]
        }
        if path.startswith("/v1/audio/video-to-audio"):
            result["videos"] = [
                {"id": "kv-9", "url": f"https://{CDN}/v.mp4", "duration": "5"}
            ]
        return ok({"task_id": "T1", "task_status": "succeed", "task_result": result})

    def posted(self, path: str) -> dict[str, Any]:
        return next(
            json.loads(r.content)
            for r in self.requests
            if r.method == "POST" and r.url.path == path
        )


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
            results.append(await call(client, results, app))
        return results


def follow(path: str = ""):
    return lambda client, results, app: client.get(
        f"/v1/videos/{results[0].json()['id']}{path}"
    )


@pytest.mark.parametrize("model", ["kling-tts", "kling-text-to-audio"])
async def test_audio_only_models_are_not_offered(tmp_path: Path, model: str):
    # The platform generates and edits video; pure audio generation is out.
    models, created = await run(
        tmp_path,
        FakeKling(),
        lambda c, r, a: c.get("/v1/models"),
        lambda c, r, a: c.post("/v1/videos", json={"model": model, "prompt": "rain"}),
    )

    assert model not in {m["id"] for m in models.json()["data"]}
    assert created.status_code in {400, 404}


async def test_speech_route_is_gone(tmp_path: Path):
    fake = FakeKling()

    (speech,) = await run(
        tmp_path,
        fake,
        lambda c, r, a: c.post(
            "/v1/audio/speech",
            json={"model": "kling-tts", "input": "Hallo", "voice": "oversea_male1"},
        ),
    )

    assert speech.status_code in {404, 405}
    assert not any(r.method == "POST" for r in fake.requests)


async def test_text_to_audio_task_is_unknown(tmp_path: Path):
    (response,) = await run(
        tmp_path,
        FakeKling(),
        lambda c, r, a: c.post(
            "/v1/videos",
            json={"model": "kling-3.0", "prompt": "rain", "task": "text_to_audio"},
        ),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_task"


async def test_video_to_audio_scores_an_earlier_kling_video(tmp_path: Path):
    fake = FakeKling()

    def create(client, results, app):
        source = app.state.provider_jobs.create(
            "kling",
            "kling-3.0",
            "text_to_video",
            {},
            upstream={
                "api": "legacy",
                "path": "/v1/videos/text2video",
                "task_id": "T0",
            },
        )
        app.state.provider_jobs.update(
            source["id"],
            status="completed",
            outputs=[
                {
                    "index": 0,
                    "stored": True,
                    "kling_video_id": "kv-1",
                    "mime_type": "video/mp4",
                }
            ],
        )
        return client.post(
            "/v1/videos",
            json={
                "model": "kling-video-to-audio",
                "prompt": "footsteps and wind",
                "references": [{"task_id": source["id"]}],
                "audio": {"bgm_prompt": "calm piano", "asmr": True},
            },
        )

    created, done, video, audio = await run(
        tmp_path,
        fake,
        create,
        follow(),
        follow("/content"),
        follow("/content?variant=audio"),
    )

    assert created.status_code == 200
    assert fake.posted("/v1/audio/video-to-audio") == {
        "video_id": "kv-1",
        "sound_effect_prompt": "footsteps and wind",
        "bgm_prompt": "calm piano",
        "asmr_mode": True,
    }
    assert done.json()["status"] == "completed"
    assert video.content == VIDEO
    assert audio.content == MP3


async def test_unknown_variants_are_rejected(tmp_path: Path):
    def finished_job(client, results, app):
        job = app.state.provider_jobs.create(
            "kling", "kling-3.0", "text_to_video", {}, upstream={"api": "legacy"}
        )
        app.state.provider_jobs.update(job["id"], status="completed")
        return client.get(f"/v1/videos/{job['id']}/content?variant=thumbnail")

    (response,) = await run(tmp_path, FakeKling(), finished_job)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_parameter"
