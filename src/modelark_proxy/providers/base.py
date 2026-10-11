"""Provider contract and model routing shared by every video backend."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from ..schemas import VideoList, VideoObject

DEFAULT_PROVIDER = "modelark"
# First match wins. Everything without a known prefix belongs to ModelArk, which
# keeps today's Seedance model IDs (and future ModelArk families) routable.
MODEL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("veo-", "google"),
    ("gemini-omni-", "google"),
    ("kling-", "kling"),
)
# Namespaces clients may put in front of a model ID, e.g. LiteLLM's `openai/`.
MODEL_NAMESPACES = ("openai/", "google/", "kling/", "modelark/")


class ProviderUnavailable(LookupError):
    """The model belongs to a provider this proxy has not configured."""


def strip_model_namespace(model: str) -> str:
    model = model.strip()
    for namespace in MODEL_NAMESPACES:
        if model.startswith(namespace):
            return model[len(namespace) :]
    return model


def provider_name_for(model: str) -> str:
    bare = strip_model_namespace(model)
    for prefix, provider in MODEL_PREFIXES:
        if bare.startswith(prefix):
            return provider
    return DEFAULT_PROVIDER


class VideoProvider(Protocol):
    name: str

    def owns_video(self, video_id: str) -> bool: ...

    async def create_video(
        self, data: dict[str, Any], upload: UploadFile | None
    ) -> VideoObject: ...

    async def list_videos(self, request: Request) -> VideoList: ...

    async def get_video(self, video_id: str) -> VideoObject: ...

    async def delete_video(self, video_id: str) -> VideoObject: ...

    async def stream_output(
        self,
        video_id: str,
        field: str,
        media_type: str,
        output: int = 0,
        variant: str = "video",
    ) -> StreamingResponse | JSONResponse: ...


class ProviderRegistry:
    def __init__(self, providers: list[VideoProvider]) -> None:
        self.providers = {provider.name: provider for provider in providers}

    def for_model(self, model: str) -> VideoProvider:
        name = provider_name_for(model)
        provider = self.providers.get(name)
        if provider is None:
            raise ProviderUnavailable(
                f"Model '{strip_model_namespace(model)}' needs the '{name}' "
                "provider, which is not configured on this proxy"
            )
        return provider

    def for_video(self, video_id: str) -> VideoProvider:
        for provider in self.providers.values():
            if provider.owns_video(video_id):
                return provider
        provider = self.providers.get(DEFAULT_PROVIDER)
        if provider is None:
            raise ProviderUnavailable(f"Video '{video_id}' is not known to this proxy")
        return provider
