"""Veo 3.1: capabilities, request mapping, and operation results.

Facts come from tasks/research/google.md and the practice notes in
prompt_guides/veo_3_1.md.
"""

from __future__ import annotations

import re
from typing import Any

from ..capabilities import Constraint, ModelCapabilities, Param, ReferenceSlot, TaskSpec
from ..unified import UnifiedRequest

LABELS = {
    "veo-3.1-generate": "Veo 3.1",
    "veo-3.1-fast-generate": "Veo 3.1 Fast",
    "veo-3.1-lite-generate": "Veo 3.1 Lite",
}
# Unified parameter → Veo `parameters` field.
PARAMETER_FIELDS = {
    "seconds": "durationSeconds",
    "resolution": "resolution",
    "aspect_ratio": "aspectRatio",
    "negative_prompt": "negativePrompt",
    "generate_audio": "generateAudio",
    "enhance_prompt": "enhancePrompt",
    "seed": "seed",
    "person_generation": "personGeneration",
}
VERTEX_OPTIONS = ("compressionQuality", "resizeMode")
IMAGE_FORMATS = ("image/jpeg", "image/png")
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TASKS = ("image_to_video", "first_last_frame", "reference_to_video")


def _frame(role: str) -> ReferenceSlot:
    return ReferenceSlot(
        role, ("image",), 1, 1, max_bytes=MAX_IMAGE_BYTES, formats=IMAGE_FORMATS
    )


def veo_family(model: str) -> str:
    return re.sub(r"-(\d{3}|preview)$", "", model)


def veo_label(model: str) -> str:
    label = LABELS.get(veo_family(model), model)
    return (
        f"{label} (Preview)" if model.endswith("-preview") or "lite" in model else label
    )


def veo_capabilities(model: str, backend: str) -> ModelCapabilities:
    family = veo_family(model)
    lite = "lite" in family
    vertex = backend == "vertex"
    parameters: dict[str, Param] = {
        "seconds": Param(values=(4, 6, 8), default=8),
        "resolution": Param(
            values=("720p", "1080p") if lite else ("720p", "1080p", "4k"),
            default="720p",
        ),
        "aspect_ratio": Param(values=("16:9", "9:16"), default="16:9"),
        "seed": Param(minimum=0, maximum=4_294_967_295),
        "person_generation": Param(
            values=("allow_adult", "allow_all", "dont_allow")
            if vertex
            else ("allow_adult", "allow_all")
        ),
        "n": Param(minimum=1, maximum=4 if vertex else 1, default=1),
    }
    if vertex:
        parameters["negative_prompt"] = Param()
        parameters["generate_audio"] = Param(default=True)
        parameters["enhance_prompt"] = Param(default=True)
    eight_seconds = {"seconds": Param(values=(8,), default=8)}
    tasks: dict[str, TaskSpec] = {
        "text_to_video": TaskSpec(),
        "image_to_video": TaskSpec(
            references=(_frame("first_frame"),), prompt_required=False
        ),
        # Practice-verified: lastFrame is rejected unless durationSeconds is 8.
        "first_last_frame": TaskSpec(
            references=(_frame("first_frame"), _frame("last_frame")),
            parameters=eight_seconds,
            prompt_required=False,
        ),
    }
    if vertex:
        # Vertex extends any 1-30 s MP4 by a fixed 7 s segment (Lite included).
        tasks["extend"] = TaskSpec(
            references=(
                ReferenceSlot(
                    "base_video",
                    ("video",),
                    1,
                    1,
                    formats=("video/mp4",),
                    min_seconds=1,
                    max_seconds=30,
                ),
            ),
            parameters={"seconds": Param(values=(7,), default=7)},
            prompt_required=False,
        )
    elif not lite:
        # The Gemini API extends its own Veo videos by 7 s, returning the whole clip.
        tasks["extend"] = TaskSpec(
            references=(
                ReferenceSlot("base_video", ("video",), 1, 1, formats=("video/mp4",)),
            ),
            parameters={
                "seconds": Param(values=(8,), default=8),
                "resolution": Param(values=("720p",), default="720p"),
            },
            prompt_required=False,
        )
    if not lite:
        tasks["reference_to_video"] = TaskSpec(
            references=(
                ReferenceSlot(
                    "reference",
                    ("image",),
                    1,
                    3,
                    max_bytes=MAX_IMAGE_BYTES,
                    formats=IMAGE_FORMATS,
                ),
            ),
            parameters=eight_seconds,
        )
    constraints = [
        Constraint(
            when={"resolution": ("1080p", "4k")},
            then={"seconds": (8,)},
            message="Veo renders 1080p and 4k only with 8 seconds",
        )
    ]
    if not vertex:
        constraints.append(
            Constraint(
                when={"task": IMAGE_TASKS},
                then={"person_generation": ("allow_adult",)},
                message="The Gemini API only allows allow_adult for image-based modes",
            )
        )
    return ModelCapabilities(
        provider="google",
        backend=backend,
        family=family,
        launch_stage="preview" if model.endswith("-preview") or lite else "ga",
        parameters=parameters,
        tasks=tasks,
        constraints=tuple(constraints),
        max_outputs=4 if vertex else 1,
        continuation="video_extension" if "extend" in tasks else "none",
        provider_options=VERTEX_OPTIONS if vertex else (),
    )


def build_veo_body(
    request: UnifiedRequest,
    caps: ModelCapabilities,
    images: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """`images` maps a reference role to Veo image objects (bytes + MIME type)."""
    params = dict(request.params)
    for name in ("seconds", "resolution", "aspect_ratio"):
        if name not in params and caps.parameters[name].default is not None:
            params[name] = caps.parameters[name].default
    parameters = {
        field: params[name]
        for name, field in PARAMETER_FIELDS.items()
        if params.get(name) is not None
    }
    if request.task == "extend" and caps.backend == "vertex":
        # Vertex extensions have a fixed length and take no duration.
        parameters.pop("durationSeconds", None)
    parameters["sampleCount"] = params.get("n", 1)
    parameters.update(request.provider_options.get("google") or {})
    instance: dict[str, Any] = {"prompt": request.prompt}
    images = images or {}
    if images.get("first_frame"):
        instance["image"] = images["first_frame"][0]
    if images.get("last_frame"):
        instance["lastFrame"] = images["last_frame"][0]
    if images.get("base_video"):
        instance["video"] = images["base_video"][0]
    if images.get("reference"):
        instance["referenceImages"] = [
            {"image": image, "referenceType": "asset"} for image in images["reference"]
        ]
    return {"instances": [instance], "parameters": parameters}


def parse_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Unified view of a Veo operation on either backend."""
    if operation.get("error"):
        error = operation["error"]
        return {
            "status": "failed",
            "error": {
                "code": "upstream_error",
                "message": str(error.get("message") or "Veo generation failed"),
                "provider_code": str(error.get("code", "")),
            },
        }
    if not operation.get("done"):
        progress = (operation.get("metadata") or {}).get("progressPercent")
        return {
            "status": "in_progress",
            "progress": int(progress) if isinstance(progress, int | float) else None,
        }
    response = operation.get("response") or {}
    result = response.get("generateVideoResponse") or response
    videos: list[dict[str, Any]] = []
    for sample in result.get("generatedSamples") or []:
        videos.append(sample.get("video") or {})
    videos.extend(result.get("videos") or [])
    outputs = [
        {
            "mime_type": video.get("mimeType") or "video/mp4",
            "bytes": video.get("bytesBase64Encoded"),
            "uri": video.get("uri") or video.get("gcsUri"),
        }
        for video in videos
        if video.get("bytesBase64Encoded") or video.get("uri") or video.get("gcsUri")
    ]
    if outputs:
        return {"status": "completed", "outputs": outputs}
    reasons = result.get("raiMediaFilteredReasons") or []
    if result.get("raiMediaFilteredCount") or reasons:
        return {
            "status": "failed",
            "error": {
                "code": "content_policy",
                "message": "; ".join(map(str, reasons))
                or "Google's safety filter blocked the video",
            },
        }
    return {
        "status": "failed",
        "error": {"code": "upstream_error", "message": "Veo returned no video"},
    }
