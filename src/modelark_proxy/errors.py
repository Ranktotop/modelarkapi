from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def openai_error(
    message: str, status: int, code: str | None = None, param: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "param": param,
                "code": code,
            }
        },
    )


class ApiError(RuntimeError):
    """An error that maps directly onto an OpenAI-style error response."""

    def __init__(
        self,
        message: str,
        status: int,
        code: str,
        *,
        retryable: bool = False,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable
        self.provider_code = provider_code

    def to_error(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": str(self)}
        if self.provider_code:
            error["provider_code"] = self.provider_code
        if self.retryable:
            error["retryable"] = True
        return error


def upstream_error(provider: str, status: int, body: Any) -> ApiError:
    """Translate an upstream HTTP error into the unified error codes (SPEC 11.3)."""
    detail = body.get("error", body) if isinstance(body, dict) else body
    message = detail.get("message") if isinstance(detail, dict) else None
    message = str(message or detail or f"HTTP {status}")
    provider_code = None
    if isinstance(detail, dict):
        provider_code = str(detail.get("status") or detail.get("code") or "") or None
    text = f"{provider} rejected the request: {message}"
    if status == 400:
        return ApiError(text, 400, "invalid_request", provider_code=provider_code)
    if status in (401, 403):
        return ApiError(text, 403, "upstream_forbidden", provider_code=provider_code)
    if status == 404:
        return ApiError(text, 404, "model_unavailable", provider_code=provider_code)
    if status == 429:
        return ApiError(
            text, 429, "rate_limited", retryable=True, provider_code=provider_code
        )
    return ApiError(
        text, 502, "upstream_error", retryable=True, provider_code=provider_code
    )
