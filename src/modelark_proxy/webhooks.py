"""Signed status webhooks for every provider (`webhook_url`).

Jobs with a webhook URL are watched; each status change becomes an event that
is queued in SQLite and delivered with Standard Webhooks signatures
(https://www.standardwebhooks.com/). Pending deliveries survive restarts and
are retried with backoff.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import sqlite3
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlparse

import httpx

from .downloads import host_is_public, system_resolver
from .retry import backoff_delay
from .schemas import VideoObject

logger = logging.getLogger(__name__)

EVENT_STATUSES = {"in_progress", "completed", "failed"}
TERMINAL_STATUSES = {"completed", "failed"}

Resolver = Callable[[str], list[str]]


def signing_key(secret: str) -> bytes:
    if secret.startswith("whsec_"):
        return base64.b64decode(secret.removeprefix("whsec_"))
    return secret.encode()


def sign(secret: str, message_id: str, timestamp: int, body: bytes) -> str:
    signed = f"{message_id}.{timestamp}.".encode() + body
    digest = hmac.new(signing_key(secret), signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("webhook_url must be an absolute https URL")


class WebhookDispatcher:
    def __init__(
        self,
        path: Path,
        secret: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = system_resolver,
        timeout_seconds: float = 10.0,
        max_attempts: int = 8,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 600.0,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret
        self.resolver = resolver
        self.max_attempts = max_attempts
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.http = httpx.AsyncClient(
            timeout=timeout_seconds, transport=transport, follow_redirects=False
        )
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.lock, self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_watches (
                    video_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at REAL NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )

    def watch(self, video_id: str, url: str, status: str) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO webhook_watches VALUES (?, ?, ?, ?)",
                (video_id, url, status, int(time.time())),
            )

    def watched(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT video_id, url, status FROM webhook_watches ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def pending(self) -> int:
        with self.lock:
            return self.connection.execute(
                "SELECT COUNT(*) FROM webhook_deliveries"
            ).fetchone()[0]

    async def check(self, get_video: Callable[[str], Awaitable[VideoObject]]) -> None:
        """Poll watched jobs and queue an event for every status change."""
        for watch in self.watched():
            try:
                video = await get_video(watch["video_id"])
            except Exception as exc:
                logger.warning(
                    "Webhook status check for %s failed: %s", watch["video_id"], exc
                )
                continue
            if video.status == watch["status"]:
                continue
            with self.lock, self.connection:
                if video.status in EVENT_STATUSES:
                    self._enqueue(watch["url"], video)
                if video.status in TERMINAL_STATUSES:
                    self.connection.execute(
                        "DELETE FROM webhook_watches WHERE video_id = ?",
                        (watch["video_id"],),
                    )
                else:
                    self.connection.execute(
                        "UPDATE webhook_watches SET status = ? WHERE video_id = ?",
                        (video.status, watch["video_id"]),
                    )

    def _enqueue(self, url: str, video: VideoObject) -> None:
        message_id = f"msg_{uuid.uuid4().hex}"
        payload = {
            "id": message_id,
            "type": f"video.{video.status}",
            "created_at": int(time.time()),
            "data": video.model_dump(mode="json"),
        }
        self.connection.execute(
            "INSERT INTO webhook_deliveries (id, url, payload, next_attempt_at, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                message_id,
                url,
                json.dumps(payload, separators=(",", ":")),
                time.time(),
                int(time.time()),
            ),
        )

    async def _target_is_public(self, url: str) -> bool:
        return await host_is_public(urlparse(url).hostname or "", self.resolver)

    async def deliver_due(self) -> None:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM webhook_deliveries WHERE next_attempt_at <= ? "
                "ORDER BY created_at",
                (time.time(),),
            ).fetchall()
        for row in rows:
            delivered = False
            error = "target does not resolve to a public address"
            if await self._target_is_public(row["url"]):
                timestamp = int(time.time())
                body = row["payload"].encode()
                try:
                    response = await self.http.post(
                        row["url"],
                        content=body,
                        headers={
                            "content-type": "application/json",
                            "webhook-id": row["id"],
                            "webhook-timestamp": str(timestamp),
                            "webhook-signature": sign(
                                self.secret, row["id"], timestamp, body
                            ),
                        },
                    )
                    delivered = response.is_success
                    error = f"HTTP {response.status_code}"
                except httpx.HTTPError as exc:
                    error = str(exc) or type(exc).__name__
            self._settle(row, delivered, error)

    def _settle(self, row: sqlite3.Row, delivered: bool, error: str) -> None:
        attempts = row["attempts"] + 1
        with self.lock, self.connection:
            if delivered or attempts >= self.max_attempts:
                if not delivered:
                    logger.warning(
                        "Dropping webhook %s to %s after %d attempts: %s",
                        row["id"],
                        row["url"],
                        attempts,
                        error,
                    )
                self.connection.execute(
                    "DELETE FROM webhook_deliveries WHERE id = ?", (row["id"],)
                )
                return
            delay = backoff_delay(
                attempts, self.retry_base_seconds, self.retry_max_seconds
            )
            self.connection.execute(
                "UPDATE webhook_deliveries SET attempts = ?, next_attempt_at = ? "
                "WHERE id = ?",
                (attempts, time.time() + delay, row["id"]),
            )

    async def close(self) -> None:
        await self.http.aclose()
        with self.lock:
            self.connection.close()
