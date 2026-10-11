"""Gemini Omni Flash: capabilities, Interactions request, and results.

Facts come from tasks/research/google.md and the live check in ADR-001
(`background: true` works on the Gemini API, GET returns the file URI).
"""

from __future__ import annotations

import re
from typing import Any

from ..capabilities import ModelCapabilities, Param, ReferenceSlot, TaskSpec
from ..unified import UnifiedRequest

LABELS = {
    "gemini-omni-1.1-flash": "Gemini Omni 1.1 Flash",
    "gemini-omni-flash": "Gemini Omni Flash",
}
IMAGE_FORMATS = ("image/png", "image/jpeg", "image/webp")
MAX_INLINE_IMAGE_BYTES = 20 * 1024 * 1024
# Unified task → Omni `video_config.task`; text_to_video leaves it to the model.
OMNI_TASKS = {
    "image_to_video": "image_to_video",
    "first_last_frame": "image_to_video",
}
RUNNING = {"in_progress", "queued", "requires_action"}


def omni_family(model: str) -> str:
    return re.sub(r"-preview$", "", model)


def omni_label(model: str) -> str:
    label = LABELS.get(omni_family(model), model)
    return f"{label} (Preview)" if model.endswith("-preview") else label


def omni_capabilities(model: str, backend: str) -> ModelCapabilities:
    family = omni_family(model)
    # The first Omni Flash preview on Vertex only does text-to-video and edits at 720p.
    limited = family == "gemini-omni-flash"
    frame = ReferenceSlot(
        "first_frame",
        ("image",),
        1,
        1,
        max_bytes=MAX_INLINE_IMAGE_BYTES,
        formats=IMAGE_FORMATS,
    )
    tasks: dict[str, TaskSpec] = {"text_to_video": TaskSpec()}
    if not limited:
        tasks["image_to_video"] = TaskSpec(references=(frame,))
        tasks["first_last_frame"] = TaskSpec(
            references=(
                frame,
                ReferenceSlot(
                    "last_frame",
                    ("image",),
                    1,
                    1,
                    max_bytes=MAX_INLINE_IMAGE_BYTES,
                    formats=IMAGE_FORMATS,
                ),
            )
        )
    return ModelCapabilities(
        provider="google",
        backend=backend,
        family=family,
        launch_stage="preview" if model.endswith("-preview") else "ga",
        parameters={
            "seconds": Param(values=tuple(range(3, 11)), default=8),
            "resolution": Param(
                values=("720p",) if limited else ("360p", "720p", "1080p", "4k"),
                default="720p",
            ),
            "aspect_ratio": Param(values=("16:9", "9:16"), default="16:9"),
        },
        tasks=tasks,
    )


def build_omni_body(
    request: UnifiedRequest,
    caps: ModelCapabilities,
    images: dict[str, list[dict[str, str]]],
    *,
    delivery_uri: bool,
) -> dict[str, Any]:
    params = dict(request.params)
    for name in ("seconds", "resolution", "aspect_ratio"):
        if name not in params:
            params[name] = caps.parameters[name].default
    response_format: dict[str, Any] = {
        "type": "video",
        "aspect_ratio": params["aspect_ratio"],
        "resolution": params["resolution"],
        "duration": f"{params['seconds']}s",
    }
    if delivery_uri:
        response_format["delivery"] = "uri"
    parts = [*images.get("first_frame", []), *images.get("last_frame", [])]
    body: dict[str, Any] = {
        "model": request.model,
        "input": [*parts, {"type": "text", "text": request.prompt}]
        if parts
        else request.prompt,
        "response_format": response_format,
        "background": True,
        "store": True,
    }
    if request.task in OMNI_TASKS:
        body["generation_config"] = {"video_config": {"task": OMNI_TASKS[request.task]}}
    return body


def parse_interaction(interaction: dict[str, Any]) -> dict[str, Any]:
    status = str(interaction.get("status") or "in_progress")
    if status in RUNNING:
        return {"status": "in_progress", "provider_status": status}
    if status != "completed":
        error = interaction.get("error") or {}
        message = error.get("message") if isinstance(error, dict) else str(error)
        return {
            "status": "failed",
            "provider_status": status,
            "error": {
                "code": "upstream_error",
                "message": message or f"Omni interaction ended with status {status}",
            },
        }
    videos = [
        part
        for step in interaction.get("steps") or []
        if step.get("type") == "model_output"
        for part in step.get("content") or []
        if part.get("type") == "video"
    ]
    if not videos:
        return {
            "status": "failed",
            "provider_status": status,
            "error": {"code": "content_policy", "message": "Omni returned no video"},
        }
    usage = interaction.get("usage") or {}
    return {
        "status": "completed",
        "provider_status": status,
        "outputs": [
            {
                "mime_type": video.get("mime_type") or "video/mp4",
                "bytes": video.get("data"),
                "uri": video.get("uri"),
            }
            for video in videos
        ],
        "usage": {"output_tokens": usage.get("total_output_tokens")},
    }
