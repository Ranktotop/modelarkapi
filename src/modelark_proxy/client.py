from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .config import Settings
from .retry import with_retry


class ModelArkError(RuntimeError):
    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ModelArkClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.ark_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.ark_api_key}"},
            timeout=settings.request_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.max_upstream_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def _send(
        self, description: str, send: Callable[[], Awaitable[httpx.Response]]
    ) -> httpx.Response:
        return await with_retry(
            send,
            attempts=self.settings.upstream_retry_attempts,
            backoff_seconds=self.settings.upstream_retry_backoff_seconds,
            max_backoff_seconds=self.settings.upstream_retry_max_backoff_seconds,
            description=f"ModelArk {description}",
        )

    async def _json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}
        if response.is_error:
            error = body.get("error", body) if isinstance(body, dict) else body
            message = (
                error.get("message", str(error))
                if isinstance(error, dict)
                else str(error)
            )
            raise ModelArkError(response.status_code, message, body)
        if not isinstance(body, dict):
            raise ModelArkError(
                502, "ModelArk returned a non-object JSON response", body
            )
        return body

    async def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._send(
            "create task",
            lambda: self.http.post("/contents/generations/tasks", json=payload),
        )
        return await self._json(response)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        response = await self._send(
            "get task",
            lambda: self.http.get(f"/contents/generations/tasks/{task_id}"),
        )
        return await self._json(response)

    async def list_tasks(self, params: list[tuple[str, str]]) -> dict[str, Any]:
        response = await self._send(
            "list tasks",
            lambda: self.http.get("/contents/generations/tasks", params=params),
        )
        return await self._json(response)

    async def validate_api_key(self) -> None:
        """Validate inference API access without creating a paid task."""
        await self.list_tasks([("page_size", "1")])

    async def delete_task(self, task_id: str) -> dict[str, Any]:
        response = await self._send(
            "delete task",
            lambda: self.http.delete(f"/contents/generations/tasks/{task_id}"),
        )
        return await self._json(response)
