"""Gemini Developer API and Vertex AI behind one interface.

Veo and Omni logic is backend-independent; only authentication, URLs, and the
operation polling call differ (docs/SPEC.md, ADR-001 decision 7).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from ..config import Settings
from ..errors import upstream_error
from ..google_auth import TokenSource
from ..retry import with_retry

VERTEX_VEO_MODELS = (
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
    "veo-3.1-lite-generate-001",
)


class GoogleBackend(Protocol):
    name: str

    async def headers(self) -> dict[str, str]: ...

    async def start_veo(self, model: str, body: dict[str, Any]) -> dict[str, Any]: ...

    async def poll_veo(self, model: str, operation: str) -> dict[str, Any]: ...

    async def list_veo_models(self) -> list[str]: ...


class _Base:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http = http

    async def headers(self) -> dict[str, str]:
        raise NotImplementedError

    async def _call(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = {**(await self.headers()), **kwargs.pop("headers", {})}
        response = await with_retry(
            lambda: self.http.request(method, url, headers=headers, **kwargs),
            attempts=self.settings.upstream_retry_attempts,
            backoff_seconds=self.settings.upstream_retry_backoff_seconds,
            max_backoff_seconds=self.settings.upstream_retry_max_backoff_seconds,
            description=f"Google {method} {url.split('?')[0]}",
        )
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}
        if response.is_error:
            raise upstream_error("Google", response.status_code, body)
        return body if isinstance(body, dict) else {"data": body}


class GeminiBackend(_Base):
    name = "gemini"

    @property
    def base(self) -> str:
        return self.settings.gemini_base_url.rstrip("/")

    async def headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.settings.gemini_api_key}

    async def start_veo(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._call(
            "POST", f"{self.base}/models/{model}:predictLongRunning", json=body
        )

    async def poll_veo(self, model: str, operation: str) -> dict[str, Any]:
        return await self._call("GET", f"{self.base}/{operation}")

    async def list_veo_models(self) -> list[str]:
        body = await self._call("GET", f"{self.base}/models", params={"pageSize": 1000})
        return [
            str(model["name"]).removeprefix("models/")
            for model in body.get("models", [])
            if str(model.get("name", "")).startswith("models/veo-3.1-")
            and "predictLongRunning" in model.get("supportedGenerationMethods", [])
        ]


class VertexBackend(_Base):
    name = "vertex"

    def __init__(
        self,
        settings: Settings,
        http: httpx.AsyncClient,
        token_source: TokenSource,
        location: str,
    ) -> None:
        super().__init__(settings, http)
        self.token_source = token_source
        self.location = location

    @property
    def host(self) -> str:
        if self.location == "global":
            return "aiplatform.googleapis.com"
        return f"{self.location}-aiplatform.googleapis.com"

    def model_url(self, model: str) -> str:
        return (
            f"https://{self.host}/v1/projects/{self.settings.vertex_project}"
            f"/locations/{self.location}/publishers/google/models/{model}"
        )

    async def headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {await self.token_source()}",
            "x-goog-user-project": self.settings.vertex_project,
        }

    async def start_veo(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._call(
            "POST", f"{self.model_url(model)}:predictLongRunning", json=body
        )

    async def poll_veo(self, model: str, operation: str) -> dict[str, Any]:
        return await self._call(
            "POST",
            f"{self.model_url(model)}:fetchPredictOperation",
            json={"operationName": operation},
        )

    async def list_veo_models(self) -> list[str]:
        available = []
        for model in VERTEX_VEO_MODELS:
            try:
                await self._call(
                    "GET",
                    f"https://{self.host}/v1beta1/publishers/google/models/{model}",
                )
            except Exception:
                continue
            available.append(model)
        return available
