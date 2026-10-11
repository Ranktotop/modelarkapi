"""Authenticated Kling API client with the error mapping from SPEC 11.3.

Kling answers with HTTP status plus a numeric `code`; HTTP 429 alone means
three different things (billing, rate limit, concurrency), so the code decides.
"""

from __future__ import annotations

from typing import Any

import httpx

from ...config import Settings
from ...errors import ApiError
from ...retry import with_retry

BILLING_CODES = {1100, 1101, 1102}
RETRYABLE_CODES = {1302, 1303}
CONTENT_CODES = {1300, 1301}
AUTH_CODES = {1000, 1001, 1002, 1003, 1004}
INVALID_CODES = {1200, 1201, 1202}


def kling_error(status: int, body: Any) -> ApiError:
    code = body.get("code") if isinstance(body, dict) else None
    message = body.get("message") if isinstance(body, dict) else None
    text = f"Kling rejected the request: {message or f'HTTP {status}'}"
    provider_code = str(code) if code is not None else None
    if code in BILLING_CODES:
        return ApiError(text, 402, "billing", provider_code=provider_code)
    if code in RETRYABLE_CODES:
        return ApiError(
            text, 429, "rate_limited", retryable=True, provider_code=provider_code
        )
    if code in CONTENT_CODES:
        return ApiError(text, 400, "content_policy", provider_code=provider_code)
    if code == 1203:
        return ApiError(text, 404, "model_unavailable", provider_code=provider_code)
    if code == 1103:
        return ApiError(text, 403, "upstream_forbidden", provider_code=provider_code)
    if code in AUTH_CODES:
        return ApiError(
            text, 503, "upstream_credentials_invalid", provider_code=provider_code
        )
    if code in INVALID_CODES or status == 400:
        return ApiError(text, 400, "invalid_request", provider_code=provider_code)
    if status == 429:
        return ApiError(
            text, 429, "rate_limited", retryable=True, provider_code=provider_code
        )
    return ApiError(
        text, 502, "upstream_error", retryable=True, provider_code=provider_code
    )


class KlingClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http = http

    @property
    def base(self) -> str:
        return self.settings.kling_base_url.rstrip("/")

    async def raw(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Send a request and return the whole Kling body, raising ApiError on failure."""
        headers = {"authorization": f"Bearer {self.settings.kling_api_key}"}
        if method == "POST":
            # POSTs create paid tasks; they are never resent, so wait for them.
            kwargs.setdefault("timeout", self.settings.create_timeout_seconds)
        response = await with_retry(
            lambda: self.http.request(
                method, f"{self.base}{path}", headers=headers, **kwargs
            ),
            attempts=self.settings.upstream_retry_attempts,
            backoff_seconds=self.settings.upstream_retry_backoff_seconds,
            max_backoff_seconds=self.settings.upstream_retry_max_backoff_seconds,
            description=f"Kling {method} {path}",
        )
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}
        if response.is_error or not isinstance(body, dict) or body.get("code", 0) != 0:
            raise kling_error(response.status_code, body)
        return body

    async def call(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send a request and return its `data`, raising ApiError on failure."""
        return (await self.raw(method, path, **kwargs)).get("data")
