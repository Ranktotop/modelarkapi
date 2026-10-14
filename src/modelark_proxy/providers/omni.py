"""Gemini Omni Flash: capabilities, Interactions request, and results.

Facts come from tasks/research/google.md and the live check in ADR-001
(`background: true` works on the Gemini API, GET returns the file URI).
"""

from __future__ import annotations

import re
from typing import Any

from ..capabilities import (
    Constraint,
    GroupLimit,
    ModelCapabilities,
    Param,
    ReferenceSlot,
    TaskSpec,
)
from ..unified import UnifiedRequest

LABELS = {
    "gemini-omni-1.1-flash": "Gemini Omni 1.1 Flash",
    "gemini-omni-flash": "Gemini Omni Flash",
}
IMAGE_FORMATS = ("image/png", "image/jpeg", "image/webp")
VIDEO_FORMATS = ("video/mp4", "video/quicktime")
MAX_INLINE_IMAGE_BYTES = 20 * 1024 * 1024
MAX_INLINE_VIDEO_BYTES = 20 * 1024 * 1024
# Unified task → Omni `video_config.task`; text_to_video leaves it to the model.
OMNI_TASKS = {
    "image_to_video": "image_to_video",
    "first_last_frame": "image_to_video",
    "reference_to_video": "reference_to_video",
    "edit": "edit",
    "extend": "extend",
}
RUNNING = {"in_progress", "queued", "requires_action"}
RATIOS = ("16:9", "9:16")
DURATIONS = tuple(range(3, 11))


def omni_family(model: str) -> str:
    return re.sub(r"-preview$", "", model)


def omni_label(model: str) -> str:
    label = LABELS.get(omni_family(model), model)
    return f"{label} (Preview)" if model.endswith("-preview") else label


def _image_slot(role: str, minimum: int, maximum: int) -> ReferenceSlot:
    return ReferenceSlot(
        role,
        ("image",),
        minimum,
        maximum,
        max_bytes=MAX_INLINE_IMAGE_BYTES,
        formats=IMAGE_FORMATS,
    )


def omni_capabilities(model: str, backend: str) -> ModelCapabilities:
    family = omni_family(model)
    # The first Omni Flash preview on Vertex only does text-to-video and edits at 720p.
    limited = family == "gemini-omni-flash"
    # An uploaded clip may be at most 10 s on the Gemini API; Vertex takes 1-30 s.
    base_video = ReferenceSlot(
        "base_video",
        ("video",),
        1,
        1,
        max_bytes=MAX_INLINE_VIDEO_BYTES,
        formats=VIDEO_FORMATS,
        max_seconds=30 if backend == "vertex" else 10,
    )
    reference_images = _image_slot("reference", 0, 10)
    tasks: dict[str, TaskSpec] = {
        "text_to_video": TaskSpec(),
        "edit": TaskSpec(
            references=(base_video,) if limited else (base_video, reference_images)
        ),
    }
    if not limited:
        tasks["image_to_video"] = TaskSpec(
            references=(_image_slot("first_frame", 1, 1),)
        )
        tasks["first_last_frame"] = TaskSpec(
            references=(
                _image_slot("first_frame", 1, 1),
                _image_slot("last_frame", 1, 1),
            )
        )
        tasks["reference_to_video"] = TaskSpec(
            references=(
                ReferenceSlot(
                    "reference",
                    ("image", "video"),
                    1,
                    13,
                    max_bytes=MAX_INLINE_VIDEO_BYTES,
                    formats=IMAGE_FORMATS + VIDEO_FORMATS,
                    max_seconds=3,
                ),
            ),
            # Up to 10 images and 3 clips of at most 3 s each.
            limits=(
                GroupLimit(roles=("reference",), types=("image",), maximum=10),
                GroupLimit(roles=("reference",), types=("video",), maximum=3),
            ),
        )
        # The extension adds `seconds` (3-10 s) at the end, up to 40 s in total.
        tasks["extend"] = TaskSpec(
            references=(base_video, reference_images), prompt_required=False
        )
    return ModelCapabilities(
        provider="google",
        backend=backend,
        family=family,
        launch_stage="preview" if model.endswith("-preview") else "ga",
        parameters={
            # "auto" and "adaptive" exist only for edits (see the constraints).
            "seconds": Param(values=(*DURATIONS, "auto"), default=8),
            "resolution": Param(
                values=("720p",) if limited else ("360p", "720p", "1080p", "4k"),
                default="720p",
            ),
            "aspect_ratio": Param(values=(*RATIOS, "adaptive"), default="16:9"),
        },
        tasks=tasks,
        constraints=(
            # Google rejects `aspect_ratio` for edits and documents no
            # `duration` there: the edit keeps the format of the input video.
            Constraint(
                when={"task": ("edit",)},
                then={"aspect_ratio": ("adaptive",), "seconds": ("auto",)},
                message="Editing keeps the aspect ratio and duration of the input video",
            ),
            Constraint(
                when={"task": tuple(task for task in tasks if task != "edit")},
                then={"aspect_ratio": RATIOS, "seconds": DURATIONS},
                message="Omni generates 16:9 or 9:16 videos of 3 to 10 seconds",
            ),
        ),
        continuation="none" if limited else "multi_turn",
    )


def build_omni_body(
    request: UnifiedRequest,
    caps: ModelCapabilities,
    media: dict[str, list[dict[str, str]]],
    *,
    delivery_uri: bool,
    previous_interaction: str | None = None,
) -> dict[str, Any]:
    """`media` maps a reference role to Interactions content parts."""
    params = dict(request.params)
    for name in ("seconds", "resolution", "aspect_ratio"):
        if name not in params:
            params[name] = caps.parameters[name].default
    response_format: dict[str, Any] = {
        "type": "video",
        "resolution": params["resolution"],
    }
    # An edit takes both from the input video ("adaptive", "auto").
    if params["aspect_ratio"] != "adaptive":
        response_format["aspect_ratio"] = params["aspect_ratio"]
    if params["seconds"] != "auto":
        response_format["duration"] = f"{params['seconds']}s"
    if delivery_uri:
        response_format["delivery"] = "uri"
    parts = [
        *media.get("first_frame", []),
        *media.get("last_frame", []),
        *media.get("reference", []),
        *media.get("base_video", []),
    ]
    text = {"type": "text", "text": request.prompt}
    body: dict[str, Any] = {
        "model": request.model,
        "input": [*parts, text] if parts or previous_interaction else request.prompt,
        "response_format": response_format,
        "background": True,
        "store": True,
    }
    if previous_interaction:
        # Multi-turn: Google continues from its own stored interaction.
        body["previous_interaction_id"] = previous_interaction
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
