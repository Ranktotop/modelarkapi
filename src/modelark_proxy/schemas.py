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
