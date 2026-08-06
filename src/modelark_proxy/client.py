from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


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
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

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
        response = await self.http.post("/contents/generations/tasks", json=payload)
        return await self._json(response)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        response = await self.http.get(f"/contents/generations/tasks/{task_id}")
        return await self._json(response)

    async def delete_task(self, task_id: str) -> dict[str, Any]:
        response = await self.http.delete(f"/contents/generations/tasks/{task_id}")
        return await self._json(response)
