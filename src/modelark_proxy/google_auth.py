"""OAuth access tokens for Vertex AI (service account file or ADC)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

TokenSource = Callable[[], Awaitable[str]]


class VertexTokenSource:
    """Hands out a valid access token, refreshing it shortly before expiry."""

    def __init__(self, credentials_file: Path | None) -> None:
        self.credentials_file = credentials_file
        self.credentials = None
        self.lock = asyncio.Lock()

    def _load(self):
        if self.credentials_file:
            return service_account.Credentials.from_service_account_file(
                str(self.credentials_file), scopes=SCOPES
            )
        credentials, _ = google.auth.default(scopes=SCOPES)
        return credentials

    def _refresh(self) -> str:
        if self.credentials is None:
            self.credentials = self._load()
        if not self.credentials.valid:
            self.credentials.refresh(google.auth.transport.requests.Request())
        return self.credentials.token

    async def __call__(self) -> str:
        async with self.lock:
            return await asyncio.to_thread(self._refresh)
