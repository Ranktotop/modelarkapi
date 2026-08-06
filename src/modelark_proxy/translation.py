from __future__ import annotations

from typing import Any

from .schemas import VideoObject

SIZE_TO_FORMAT: dict[str, tuple[str, str]] = {
    "864x496": ("480p", "16:9"),
    "752x560": ("480p", "4:3"),
    "640x640": ("480p", "1:1"),
    "560x752": ("480p", "3:4"),
    "496x864": ("480p", "9:16"),
    "992x432": ("480p", "21:9"),
    "1280x720": ("720p", "16:9"),
    "1112x834": ("720p", "4:3"),
    "960x960": ("720p", "1:1"),
    "834x1112": ("720p", "3:4"),
    "720x1280": ("720p", "9:16"),
    "1470x630": ("720p", "21:9"),
    "1920x1080": ("1080p", "16:9"),
    "1664x1248": ("1080p", "4:3"),
    "1440x1440": ("1080p", "1:1"),
    "1248x1664": ("1080p", "3:4"),
    "1080x1920": ("1080p", "9:16"),
    "2206x946": ("1080p", "21:9"),
    "3840x2160": ("4K", "16:9"),
    "3326x2494": ("4K", "4:3"),
    "2880x2880": ("4K", "1:1"),
    "2494x3326": ("4K", "3:4"),
    "2160x3840": ("4K", "9:16"),
    "4398x1886": ("4K", "21:9"),
}

FORMAT_TO_SIZE = {value: key for key, value in SIZE_TO_FORMAT.items()}

STATUS_MAP = {
    "queued": "queued",
    "running": "in_progress",
    "succeeded": "completed",
    "failed": "failed",
    "cancelled": "failed",
    "expired": "failed",
}


class TranslationError(ValueError):
    pass


def apply_openai_format(payload: dict[str, Any], size: str | None) -> None:
    if not size:
        return
    try:
        resolution, ratio = SIZE_TO_FORMAT[size]
    except KeyError as exc:
        supported = ", ".join(sorted(SIZE_TO_FORMAT))
        raise TranslationError(
            f"Unsupported size '{size}'. Supported values: {supported}"
        ) from exc
    payload.setdefault("resolution", resolution)
    payload.setdefault("ratio", ratio)


def byteplus_to_openai(data: dict[str, Any]) -> VideoObject:
    provider_status = str(data.get("status", "queued"))
    status = STATUS_MAP.get(provider_status, provider_status)
    error = data.get("error")
    if status == "failed" and not error:
        error = {
            "code": f"task_{provider_status}",
            "message": f"ModelArk task is {provider_status}",
        }

    progress = 0
    if status == "in_progress":
        progress = 50
    elif status in {"completed", "failed"}:
        progress = 100

    resolution = data.get("resolution")
    ratio = data.get("ratio")
    size = FORMAT_TO_SIZE.get((resolution, ratio))
    created_at = data.get("created_at")
    updated_at = data.get("updated_at")
    completed_at = updated_at if status == "completed" else None
    expires_at = completed_at + 86_400 if completed_at else None

    return VideoObject(
        id=str(data["id"]),
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        expires_at=expires_at,
        error=error,
        progress=progress,
        seconds=str(data["duration"]) if data.get("duration") is not None else None,
        size=size,
        model=data.get("model"),
        usage=data.get("usage"),
        provider_status=provider_status,
        last_frame_available=isinstance(
            (data.get("content") or {}).get("last_frame_url"), str
        ),
        service_tier=data.get("service_tier"),
    )
