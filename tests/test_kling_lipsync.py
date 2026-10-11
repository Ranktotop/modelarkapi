"""Kling lip sync (multi-step worker) and avatar (T18)."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_video_id

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 24
WAV_URI = "data:audio/wav;base64," + base64.b64encode(WAV).decode()
RESULT_URL = "https://v1-kling.klingai.com/result.mp4"
VIDEO = b"\x00\x00\x00\x20ftypisomlipsync"


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        ok = lambda data: httpx.Response(200, json={"code": 0, "data": data})
        if request.url.host == "v1-kling.klingai.com":
            return httpx.Response(
                200, content=VIDEO, headers={"content-type": "video/mp4"}
            )
        if path == "/v1/videos/identify-face":
            return ok(
                {
                    "session_id": "S1",
                    "face_data": [
                        {"face_id": "short", "start_time": 0, "end_time": 1500},
                        {"face_id": "long", "start_time": 1000, "end_time": 9000},
                    ],
                }
            )
        if path == "/v1/audio/tts":
            return ok(
                {
                    "task_id": "A",
                    "task_status": "succeed",
                    "task_result": {
                        "audios": [
                            {
                                "id": "aud-1",
                                "url": "https://v1-kling.klingai.com/a.mp3",
                                "duration": "3.2",
                            }
                        ]
                    },
                }
            )
        if request.method == "POST":
            return ok({"task_id": "T1", "task_status": "submitted"})
        return ok(
            {
                "task_id": "T1",
                "task_status": "succeed",
                "task_result": {
                    "videos": [{"id": "kv-2", "url": RESULT_URL, "duration": "5"}]
                },
            }
        )

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
        provider_poll_interval_seconds=0.01,
    )


async def finished(client: httpx.AsyncClient, video_id: str) -> dict[str, Any]:
    for _ in range(200):
        body = (await client.get(f"/v1/videos/{video_id}")).json()
        if body["status"] in {"completed", "failed"}:
            return body
        await asyncio.sleep(0.01)
    raise AssertionError("job did not finish")


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
        return await scenario(client, app)


async def test_lip_sync_identifies_the_face_speaks_the_text_and_renders(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client, app):
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
        created = await client.post(
            "/v1/videos",
            json={
                "model": "kling-lip-sync",
                "references": [{"task_id": source["id"]}],
                "speech": {
                    "text": "Hello there",
                    "voice": "oversea_male1",
                    "language": "en",
                },
                "audio": {"volume": 1.5},
            },
        )
        assert created.status_code == 200
        assert created.json()["status"] == "queued"
        done = await finished(client, created.json()["id"])
        content = await client.get(f"/v1/videos/{created.json()['id']}/content")
        return created, done, content

    created, done, content = await run(tmp_path, fake, scenario)

    assert decode_video_id(created.json()["id"]).startswith("vid-kling-")
    assert fake.posted("/v1/videos/identify-face") == {"video_id": "kv-1"}
    assert fake.posted("/v1/audio/tts") == {
        "text": "Hello there",
        "voice_id": "oversea_male1",
        "voice_language": "en",
        "voice_speed": 1.0,
    }
    assert fake.posted("/v1/videos/advanced-lip-sync") == {
        "session_id": "S1",
        "face_choose": [
            {
                "face_id": "long",
                "audio_id": "aud-1",
                "sound_start_time": 0,
                "sound_end_time": 3200,
                "sound_insert_time": 1000,
                "sound_volume": 1.5,
            }
        ],
    }
    assert done["status"] == "completed"
    assert content.content == VIDEO


async def test_lip_sync_with_uploaded_audio_and_external_video(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client, app):
        created = await client.post(
            "/v1/videos",
            json={
                "model": "kling-lip-sync",
                "references": [
                    {"type": "video", "url": "https://videos.example.com/talk.mp4"},
                    {"type": "audio", "url": WAV_URI},
                ],
                "audio": {"face_id": "short", "end_ms": 2500, "insert_at_ms": 0},
            },
        )
        return await finished(client, created.json()["id"])

    done = await run(tmp_path, fake, scenario)

    assert done["status"] == "completed"
    assert fake.posted("/v1/videos/identify-face") == {
        "video_url": "https://videos.example.com/talk.mp4"
    }
    choice = fake.posted("/v1/videos/advanced-lip-sync")["face_choose"][0]
    assert choice["face_id"] == "short"
    assert choice["sound_file"] == base64.b64encode(WAV).decode()
    assert (
        choice["sound_start_time"],
        choice["sound_end_time"],
        choice["sound_insert_time"],
    ) == (0, 2500, 0)


def wav_of(milliseconds: int) -> bytes:
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * (8 * milliseconds))
    return buffer.getvalue()


async def test_lip_sync_ends_with_shorter_audio(tmp_path: Path):
    fake = FakeKling()
    clip = "data:audio/wav;base64," + base64.b64encode(wav_of(2000)).decode()

    async def scenario(client, app):
        created = await client.post(
            "/v1/videos",
            json={
                "model": "kling-lip-sync",
                "references": [
                    {"type": "video", "url": "https://videos.example.com/talk.mp4"},
                    {"type": "audio", "url": clip},
                ],
                "audio": {"face_id": "long"},
            },
        )
        return await finished(client, created.json()["id"])

    done = await run(tmp_path, fake, scenario)

    assert done["status"] == "completed"
    choice = fake.posted("/v1/videos/advanced-lip-sync")["face_choose"][0]
    # The face is visible for 8 s, but the audio only lasts 2 s.
    assert choice["sound_end_time"] == 2000


async def test_lip_sync_needs_speech_or_audio(tmp_path: Path):
    async def scenario(client, app):
        return await client.post(
            "/v1/videos",
            json={
                "model": "kling-lip-sync",
                "references": [
                    {"type": "video", "url": "https://videos.example.com/talk.mp4"}
                ],
            },
        )

    response = await run(tmp_path, FakeKling(), scenario)

    assert response.status_code == 400


async def test_avatar_speaks_from_an_image(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client, app):
        created = await client.post(
            "/v1/videos",
            json={
                "model": "kling-avatar",
                "prompt": "friendly, nodding",
                "quality": "pro",
                "references": [{"type": "image", "url": PNG_URI}],
                "speech": {"text": "Welcome", "voice": "oversea_male1"},
            },
        )
        done = await finished(client, created.json()["id"])
        return done

    done = await run(tmp_path, fake, scenario)

    assert done["status"] == "completed"
    assert fake.posted("/v1/videos/avatar/image2video") == {
        "image": base64.b64encode(PNG).decode(),
        "audio_id": "aud-1",
        "prompt": "friendly, nodding",
        "mode": "pro",
    }
    poll = next(
        r
        for r in fake.requests
        if r.method == "GET" and r.url.path.startswith("/v1/videos/avatar")
    )
    assert poll.url.path == "/v1/videos/avatar/image2video/T1"


async def test_avatar_passes_audio_urls_through(tmp_path: Path):
    fake = FakeKling()

    async def scenario(client, app):
        return await client.post(
            "/v1/videos",
            json={
                "model": "kling-avatar",
                "references": [
                    {"type": "image", "url": PNG_URI},
                    {"type": "audio", "url": "https://audio.example.com/voice.mp3"},
                ],
            },
        )

    created = await run(tmp_path, fake, scenario)

    assert created.status_code == 200
    assert (
        fake.posted("/v1/videos/avatar/image2video")["sound_file"]
        == "https://audio.example.com/voice.mp3"
    )


@pytest.mark.parametrize("model", ["kling-lip-sync", "kling-avatar"])
async def test_virtual_models_are_listed(tmp_path: Path, model: str):
    async def scenario(client, app):
        return (await client.get("/v1/models")).json()["data"]

    models = {m["id"]: m for m in await run(tmp_path, FakeKling(), scenario)}

    assert models[model]["virtual"] is True
    assert list(models[model]["capabilities"]["tasks"]) == [
        model.removeprefix("kling-").replace("-", "_")
    ]
