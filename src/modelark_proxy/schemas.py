from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class VideoObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    object: str = "video"
    status: str
    created_at: int | None = None
    completed_at: int | None = None
    expires_at: int | None = None
    error: dict[str, Any] | None = None
    progress: int | None = None
    remixed_from_video_id: str | None = None
    seconds: str | None = None
    size: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None


class VideoList(BaseModel):
    object: str = "list"
    data: list[VideoObject]
    total: int | None = None
    page_num: int | None = None
    page_size: int | None = None
    has_more: bool | None = None


class MediaReference(BaseModel):
    id: str
    url: str
    media_type: str
    kind: str
    filename: str | None = None
    expires_at: int


class MediaReferenceList(BaseModel):
    object: str = "list"
    data: list[MediaReference]
