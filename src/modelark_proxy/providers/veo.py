"""Veo 3.1: capabilities, request mapping, and operation results.

Facts come from tasks/research/google.md and the practice notes in
prompt_guides/veo_3_1.md.
"""

from __future__ import annotations

import re
from typing import Any

from ..capabilities import Constraint, ModelCapabilities, Param, TaskSpec
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
    return ModelCapabilities(
        provider="google",
        backend=backend,
        family=family,
        launch_stage="preview" if model.endswith("-preview") or lite else "ga",
        parameters=parameters,
        tasks={"text_to_video": TaskSpec()},
        constraints=(
            Constraint(
                when={"resolution": ("1080p", "4k")},
                then={"seconds": (8,)},
                message="Veo renders 1080p and 4k only with 8 seconds",
            ),
        ),
        max_outputs=4 if vertex else 1,
        provider_options=VERTEX_OPTIONS if vertex else (),
    )


def build_veo_body(request: UnifiedRequest, caps: ModelCapabilities) -> dict[str, Any]:
    params = dict(request.params)
    for name in ("seconds", "resolution", "aspect_ratio"):
        if name not in params and caps.parameters[name].default is not None:
            params[name] = caps.parameters[name].default
    parameters = {
        field: params[name]
        for name, field in PARAMETER_FIELDS.items()
        if params.get(name) is not None
    }
    parameters["sampleCount"] = params.get("n", 1)
    parameters.update(request.provider_options.get("google") or {})
    return {"instances": [{"prompt": request.prompt}], "parameters": parameters}


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
