from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from modelark_proxy.downloads import stream_remote
from modelark_proxy.outputs import OutputStore
from modelark_proxy.provider_jobs import ProviderJobStore, purge_expired
from modelark_proxy.retry import TransientUpstreamError
from modelark_proxy.workers import JobRunner


async def chunks(*parts: bytes):
    for part in parts:
        yield part


def test_created_job_has_provider_scoped_id_and_round_trips(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=3600)

    job = store.create(
        "google",
        "veo-3.1-fast-generate-001",
        "text_to_video",
        {"prompt": "fox"},
        slug="veo",
        upstream={"operation": "projects/p/operations/1"},
    )

    assert re.fullmatch(r"vid-veo-[0-9a-f]{32}", job["id"])
    assert store.get(job["id"]) == job
    assert job["status"] == "queued"
    assert job["request"] == {"prompt": "fox"}
    assert job["upstream"] == {"operation": "projects/p/operations/1"}
    assert job["expires_at"] >= int(time.time()) + 3599


def test_jobs_survive_a_restart(tmp_path: Path):
    path = tmp_path / "jobs.db"
    job = ProviderJobStore(path, ttl_seconds=60).create(
        "kling", "kling-3.0", "text_to_video", {}
    )

    ProviderJobStore(path, ttl_seconds=60).update(
        job["id"], status="in_progress", state={"step": "face_identification"}
    )
    reloaded = ProviderJobStore(path, ttl_seconds=60).get(job["id"])

    assert reloaded["status"] == "in_progress"
    assert reloaded["state"] == {"step": "face_identification"}


def test_unknown_fields_are_rejected(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    job = store.create("kling", "kling-3.0", "text_to_video", {})

    with pytest.raises(ValueError):
        store.update(job["id"], id="other")


def test_job_converts_to_video_object(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    job = store.create(
        "google", "veo-3.1-generate-001", "text_to_video", {"seconds": 8}, slug="veo"
    )
    store.update(
        job["id"],
        status="completed",
        provider_status="done",
        outputs=[{"index": 0, "variants": ["video"], "mime_type": "video/mp4"}],
        usage={"provider": "google"},
    )

    video = store.to_video(store.get(job["id"]))

    assert video.id == job["id"]
    assert video.status == "completed"
    assert video.progress == 100
    assert video.model == "veo-3.1-generate-001"
    assert video.seconds == "8"
    assert video.provider == "google"
    assert video.task == "text_to_video"
    assert video.outputs[0]["mime_type"] == "video/mp4"
    assert video.completed_at is not None


async def test_outputs_are_stored_and_purged_with_expired_jobs(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    outputs = OutputStore(tmp_path / "outputs")
    expired = store.create("google", "veo", "text_to_video", {})
    kept = store.create("google", "veo", "text_to_video", {})
    saved = await outputs.save(
        expired["id"], 0, "video", chunks(b"ab", b"cd"), "video/mp4"
    )
    store.update(expired["id"], expires_at=int(time.time()) - 1)

    purged = purge_expired(store, outputs)

    assert saved["bytes"] == 4
    assert purged == [expired["id"]]
    assert store.get(expired["id"]) is None
    assert outputs.path(expired["id"], 0, "video") is None
    assert store.get(kept["id"]) is not None


async def test_output_paths_cannot_escape_the_store(tmp_path: Path):
    outputs = OutputStore(tmp_path / "outputs")

    with pytest.raises(ValueError):
        await outputs.save("../evil", 0, "video", chunks(b"x"), "video/mp4")


async def test_runner_resumes_unfinished_worker_jobs(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    pending = store.create("kling", "kling-lip-sync", "lip_sync", {}, worker=True)
    store.create("kling", "kling-3.0", "text_to_video", {})  # polled lazily
    done = store.create("kling", "kling-lip-sync", "lip_sync", {}, worker=True)
    store.update(done["id"], status="completed")
    seen: list[str] = []

    async def handler(job):
        seen.append(job["id"])
        store.update(job["id"], status="completed")

    runner = JobRunner(store, concurrency=2)
    runner.register("kling", handler)
    runner.resume()
    await runner.wait_idle()
    await runner.close()

    assert seen == [pending["id"]]


async def test_runner_limits_parallel_handlers(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    jobs = [
        store.create("google", "omni", "text_to_video", {}, worker=True)
        for _ in range(5)
    ]
    active = 0
    peak = 0

    async def handler(job):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        store.update(job["id"], status="completed")

    runner = JobRunner(store, concurrency=2)
    runner.register("google", handler)
    for job in jobs:
        runner.schedule(job["id"])
    await runner.wait_idle()
    await runner.close()

    assert peak == 2
    assert all(store.get(job["id"])["status"] == "completed" for job in jobs)


async def test_runner_retries_transient_errors_and_fails_on_others(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    flaky = store.create("google", "omni", "text_to_video", {}, worker=True)
    broken = store.create("google", "omni", "text_to_video", {}, worker=True)
    attempts = 0

    async def handler(job):
        nonlocal attempts
        if job["id"] == broken["id"]:
            raise RuntimeError("boom")
        attempts += 1
        if attempts == 1:
            raise TransientUpstreamError("dns")
        store.update(job["id"], status="completed")

    runner = JobRunner(
        store, concurrency=2, retry_base_seconds=0.001, retry_max_seconds=0.001
    )
    runner.register("google", handler)
    runner.schedule(flaky["id"])
    runner.schedule(broken["id"])
    await runner.wait_idle()
    await runner.close()

    assert store.get(flaky["id"])["status"] == "completed"
    failed = store.get(broken["id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "upstream_error"


async def test_remote_stream_follows_only_allowed_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.example.com":
            assert request.headers["x-goog-api-key"] == "k"
            return httpx.Response(
                302, headers={"location": "https://cdn.example.com/v.mp4"}
            )
        if request.url.host == "cdn.example.com":
            assert "x-goog-api-key" not in request.headers
            return httpx.Response(
                200, content=b"video", headers={"content-type": "video/mp4"}
            )
        return httpx.Response(302, headers={"location": "https://evil.test/x"})

    transport = httpx.MockTransport(handler)
    response = await stream_remote(
        "https://api.example.com/file",
        headers={"x-goog-api-key": "k"},
        allowed_host_suffixes=[".example.com"],
        transport=transport,
        timeout=5,
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert body == b"video"
    assert response.media_type == "video/mp4"

    with pytest.raises(HTTPException) as denied:
        await stream_remote(
            "https://other.example.com/file",
            headers={},
            allowed_host_suffixes=[".example.com"],
            transport=transport,
            timeout=5,
        )
    assert denied.value.status_code == 502


async def test_runner_waits_between_polls_of_an_unfinished_job(tmp_path: Path):
    store = ProviderJobStore(tmp_path / "jobs.db", ttl_seconds=60)
    job = store.create("google", "omni", "text_to_video", {}, worker=True)
    calls: list[float] = []

    async def handler(current):
        calls.append(asyncio.get_running_loop().time())
        if len(calls) == 3:
            store.update(current["id"], status="completed")

    runner = JobRunner(store, concurrency=1, poll_interval_seconds=0.05)
    runner.register("google", handler)
    runner.schedule(job["id"])
    await runner.wait_idle()
    await runner.close()

    assert len(calls) == 3
    assert calls[2] - calls[0] >= 0.09


async def test_app_purges_expired_provider_jobs_on_startup(tmp_path: Path):
    from modelark_proxy.app import create_app
    from modelark_proxy.config import Settings

    settings = Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
    )
    store = ProviderJobStore(settings.provider_job_db, ttl_seconds=60)
    outputs = OutputStore(settings.output_dir)
    job = store.create("google", "veo", "text_to_video", {})
    await outputs.save(job["id"], 0, "video", chunks(b"x"), "video/mp4")
    store.update(job["id"], expires_at=int(time.time()) - 1)

    app = create_app(settings, validate_startup_credentials=False)
    async with app.router.lifespan_context(app):
        assert app.state.provider_jobs.get(job["id"]) is None

    assert outputs.path(job["id"], 0, "video") is None
