from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.schemas import VideoObject
from modelark_proxy.webhooks import WebhookDispatcher

SECRET = "whsec_" + base64.b64encode(b"super-secret-signing-key").decode()


def verify_standard_webhook(secret: str, headers: httpx.Headers, body: bytes) -> bool:
    """Reference check following https://www.standardwebhooks.com/ ."""
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{headers['webhook-id']}.{headers['webhook-timestamp']}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(
        part.split(",", 1)[1] == expected
        for part in headers["webhook-signature"].split(" ")
    )


def public_resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


class Upstream:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = statuses

    async def get(self, video_id: str) -> VideoObject:
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return VideoObject(id=f"video_public_{video_id}", status=status)


def receiver(received: list[httpx.Request], status_code: int = 204):
    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(status_code)

    return httpx.MockTransport(handler)


async def test_status_changes_are_delivered_as_signed_events(tmp_path: Path):
    received: list[httpx.Request] = []
    dispatcher = WebhookDispatcher(
        tmp_path / "hooks.db",
        SECRET,
        transport=receiver(received),
        resolver=public_resolver,
    )
    dispatcher.watch("cgt-1", "https://hooks.example.com/video", "queued")
    upstream = Upstream(["queued", "in_progress", "in_progress", "completed"])

    for _ in range(4):
        await dispatcher.check(upstream.get)
        await dispatcher.deliver_due()

    events = [json.loads(request.content) for request in received]
    assert [event["type"] for event in events] == [
        "video.in_progress",
        "video.completed",
    ]
    assert events[1]["data"]["id"] == "video_public_cgt-1"
    assert all(
        verify_standard_webhook(SECRET, request.headers, request.content)
        for request in received
    )
    assert dispatcher.watched() == []


async def test_failed_deliveries_survive_a_restart_and_are_retried(tmp_path: Path):
    path = tmp_path / "hooks.db"
    failing: list[httpx.Request] = []
    first = WebhookDispatcher(
        path,
        SECRET,
        transport=receiver(failing, status_code=503),
        resolver=public_resolver,
        retry_base_seconds=0,
    )
    first.watch("cgt-1", "https://hooks.example.com/video", "queued")
    await first.check(Upstream(["completed"]).get)
    await first.deliver_due()

    delivered: list[httpx.Request] = []
    second = WebhookDispatcher(
        path,
        SECRET,
        transport=receiver(delivered),
        resolver=public_resolver,
        retry_base_seconds=0,
    )
    await second.deliver_due()

    assert len(failing) == 1
    assert len(delivered) == 1
    assert delivered[0].headers["webhook-id"] == failing[0].headers["webhook-id"]
    assert second.pending() == 0


async def test_private_targets_are_never_called(tmp_path: Path):
    received: list[httpx.Request] = []
    dispatcher = WebhookDispatcher(
        tmp_path / "hooks.db",
        SECRET,
        transport=receiver(received),
        resolver=lambda host: ["10.0.0.5"],
        max_attempts=1,
    )
    dispatcher.watch("cgt-1", "https://internal.example.com/hook", "queued")
    await dispatcher.check(Upstream(["completed"]).get)
    await dispatcher.deliver_due()

    assert received == []
    assert dispatcher.pending() == 0


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
    )


async def post_video(
    settings: Settings,
    body: dict,
    captured: list[httpx.Request],
    resolver=public_resolver,
):
    def modelark(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": "cgt-1"})

    app = create_app(
        settings,
        ark_transport=httpx.MockTransport(modelark),
        webhook_resolver=resolver,
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post("/v1/videos", json=body)
        return response, app.state.webhooks.watched()


async def test_webhook_url_requires_a_signing_secret(settings: Settings):
    captured: list[httpx.Request] = []
    response, _ = await post_video(
        settings,
        {
            "model": "dreamina-seedance-2-5-260628",
            "prompt": "fox",
            "webhook_url": "https://hooks.example.com/video",
        },
        captured,
    )

    assert response.status_code == 400
    assert "WEBHOOK_SECRET" in response.json()["error"]["message"]
    assert captured == []


async def test_webhook_url_is_watched_and_not_sent_to_modelark(settings: Settings):
    settings.webhook_secret = SECRET
    captured: list[httpx.Request] = []
    response, watched = await post_video(
        settings,
        {
            "model": "dreamina-seedance-2-5-260628",
            "prompt": "fox",
            "webhook_url": "https://hooks.example.com/video",
            "callback_url": "https://client.example.com/modelark",
        },
        captured,
    )

    assert response.status_code == 200
    upstream = json.loads(captured[0].content)
    assert "webhook_url" not in upstream
    assert upstream["callback_url"] == "https://client.example.com/modelark"
    assert watched == [
        {
            "video_id": "cgt-1",
            "url": "https://hooks.example.com/video",
            "status": "queued",
        }
    ]


async def test_webhook_url_must_use_https(settings: Settings):
    settings.webhook_secret = SECRET
    response, _ = await post_video(
        settings,
        {
            "model": "dreamina-seedance-2-5-260628",
            "prompt": "fox",
            "webhook_url": "http://x.example.com",
        },
        [],
    )

    assert response.status_code == 400


async def test_private_webhook_targets_are_rejected_at_create(settings: Settings):
    settings.webhook_secret = SECRET
    captured: list[httpx.Request] = []

    response, watched = await post_video(
        settings,
        {
            "model": "dreamina-seedance-2-5-260628",
            "prompt": "fox",
            "webhook_url": "https://intranet.example.com/hook",
        },
        captured,
        resolver=lambda host: ["10.0.0.5"],
    )

    assert response.status_code == 400
    assert captured == []
    assert watched == []
