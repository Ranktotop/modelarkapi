"""Normalization of the unified `POST /v1/videos` request (docs/SPEC.md 5–8).

Turns the many accepted spellings (OpenAI fields, legacy Seedance fields,
typed references) into one shape and resolves the task when the client did
not name it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .translation import SIZE_TO_FORMAT
from .validation import ContractError

TASKS = (
    "text_to_video",
    "image_to_video",
    "first_last_frame",
    "reference_to_video",
    "multi_shot",
    "edit",
    "extend",
    "stitch",
    "motion_control",
    "lip_sync",
    "avatar",
    "effect",
    "multi_element_edit",
    "video_to_audio",
    "text_to_audio",
    "commerce_talking_agent",
    "commerce_goods_studio",
    "commerce_apparel",
)
REFERENCE_TYPES = {"image", "video", "audio", "element", "voice"}
SOURCES = ("url", "upload_id", "task_id", "asset_id")
UNIFIED_PARAMS = (
    "seconds",
    "resolution",
    "aspect_ratio",
    "negative_prompt",
    "seed",
    "generate_audio",
    "quality",
    "n",
    "shots",
    "shot_mode",
    "effect",
    "speech",
    "audio",
    "selections",
    "edit_mode",
    "commerce",
    "watermark",
    "enhance_prompt",
    "person_generation",
    "output_format",
    "return_last_frame",
)
# Accepted request fields that are not unified parameters.
STRUCTURAL_FIELDS = {
    "model",
    "prompt",
    "task",
    "references",
    "size",
    "ratio",
    "duration",
    "provider_options",
    "parameter_policy",
    "user",
    "metadata",
    "input_reference_url",
    "input_reference_media_type",
    "input_reference_role",
    "reference_urls",
    "real_human",
    "omni_reference_task_type",
}
LEGACY_ROLES = {"reference_image", "reference_video", "reference_audio"}
LEGACY_TASKS = {
    "reference": "reference_to_video",
    "edit": "edit",
    "extend": "extend",
}
ASSET_TYPES = {
    "asset-kling-element-": "element",
    "asset-kling-voice-": "voice",
    "asset-modelark-": "image",
}
ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4", "21:9")
# Pixel area of each resolution tier at 16:9, compared on a log scale.
TIER_AREAS = {
    "360p": 640 * 360,
    "480p": 854 * 480,
    "720p": 1280 * 720,
    "1080p": 1920 * 1080,
    "4k": 3840 * 2160,
}
BASE_VIDEO_TASKS = {
    "edit",
    "extend",
    "lip_sync",
    "video_to_audio",
    "multi_element_edit",
}
SUBJECT_TASKS = {"motion_control", "avatar", "effect"}


@dataclass
class UnifiedRequest:
    model: str
    task: str
    prompt: str
    references: list[dict[str, Any]]
    params: dict[str, Any]
    provider_options: dict[str, Any] = field(default_factory=dict)
    policy: str = "strict"
    explicit_task: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def _seconds(value: Any) -> int | float | str:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"auto", "-1"}:
            return "auto"
        try:
            number = float(text)
        except ValueError as exc:
            raise ContractError(
                "seconds must be a number or 'auto'", param="seconds"
            ) from exc
    elif isinstance(value, int | float) and not isinstance(value, bool):
        number = float(value)
    else:
        raise ContractError("seconds must be a number or 'auto'", param="seconds")
    if number == -1:
        return "auto"
    return int(number) if number.is_integer() else number


def _aspect_from_dimensions(width: int, height: int) -> str:
    target = math.log(width / height)
    return min(
        ASPECT_RATIOS,
        key=lambda ratio: abs(
            math.log(int(ratio.split(":")[0]) / int(ratio.split(":")[1])) - target
        ),
    )


def _size(value: Any) -> tuple[str, str]:
    if value in SIZE_TO_FORMAT:
        return SIZE_TO_FORMAT[value]
    try:
        width, height = (int(part) for part in str(value).lower().split("x"))
        if width <= 0 or height <= 0:
            raise ValueError
    except ValueError as exc:
        raise ContractError(
            "size must use the form WIDTHxHEIGHT, e.g. 1280x720", param="size"
        ) from exc
    area = math.log(width * height)
    tier = min(TIER_AREAS, key=lambda name: abs(math.log(TIER_AREAS[name]) - area))
    return tier, _aspect_from_dimensions(width, height)


def _reference(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        item = {"url": item, "type": "image"}
    if not isinstance(item, dict):
        raise ContractError("Each reference must be an object", param="references")
    reference = dict(item)
    if "media_type" in reference and "type" not in reference:
        reference["type"] = str(reference.pop("media_type")).split("/", 1)[0]
    sources = [key for key in SOURCES if reference.get(key)]
    if len(sources) != 1:
        raise ContractError(
            "Each reference needs exactly one of url, upload_id, task_id, asset_id",
            param="references",
        )
    if "type" not in reference:
        if reference.get("task_id"):
            reference["type"] = "video"
        elif reference.get("asset_id"):
            prefix = next(
                (p for p in ASSET_TYPES if str(reference["asset_id"]).startswith(p)),
                None,
            )
            if prefix is None:
                raise ContractError(
                    "Reference type is required for this asset", param="references"
                )
            reference["type"] = ASSET_TYPES[prefix]
        else:
            raise ContractError("Each reference needs a type", param="references")
    if reference["type"] not in REFERENCE_TYPES:
        raise ContractError(
            "Reference type must be image, video, audio, element, or voice",
            param="references",
        )
    if reference.get("role") in LEGACY_ROLES:
        # Seedance's generic roles carry no task meaning; let the task decide.
        reference.pop("role")
    return reference


def _legacy_references(data: dict[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    url = data.get("input_reference_url")
    if isinstance(url, str):
        references.append(
            _reference(
                {
                    "url": url,
                    "type": data.get("input_reference_media_type") or "video",
                    **(
                        {"role": data["input_reference_role"]}
                        if data.get("input_reference_role")
                        else {}
                    ),
                    **({"real_human": True} if data.get("real_human") is True else {}),
                }
            )
        )
    items = data.get("reference_urls") or []
    for item in [items] if isinstance(items, str) else items:
        references.append(_reference(item))
    return references


def _infer_task(references: list[dict[str, Any]], params: dict[str, Any]) -> str:
    roles = {reference.get("role") for reference in references}
    has_speech = any(
        reference["type"] == "audio" and reference.get("role") == "speech"
        for reference in references
    ) or bool((params.get("speech") or {}).get("text"))
    images = [reference for reference in references if reference["type"] == "image"]
    if params.get("effect"):
        return "effect"
    if params.get("selections"):
        return "multi_element_edit"
    if "motion" in roles:
        return "motion_control"
    if params.get("shots"):
        return "multi_shot"
    if "base_video" in roles and has_speech:
        return "lip_sync"
    if "base_video" in roles:
        return "edit"
    if {"first_frame", "last_frame"} <= roles:
        return "first_last_frame"
    if (
        len(references) == 1
        and images
        and images[0].get("role") in {None, "first_frame"}
    ):
        return "image_to_video"
    if references:
        return "reference_to_video"
    return "text_to_video"


def _default_role(reference: dict[str, Any], task: str, frames_taken: list[str]) -> str:
    """Role for a reference without one; `frames_taken` tracks single-use roles."""
    kind = reference["type"]
    if kind == "image":
        if task == "image_to_video":
            return "first_frame"
        if task == "first_last_frame":
            role = "first_frame" if "first_frame" not in frames_taken else "last_frame"
            frames_taken.append(role)
            return role
        if task in SUBJECT_TASKS:
            return "subject"
    if kind == "video":
        if task in BASE_VIDEO_TASKS and "base_video" not in frames_taken:
            frames_taken.append("base_video")
            return "base_video"
        if task == "motion_control":
            return "motion"
    if kind == "audio" and task in {"lip_sync", "avatar"}:
        return "speech"
    return "reference"


def normalize_request(
    data: dict[str, Any], *, default_policy: str = "strict"
) -> UnifiedRequest:
    model = data.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ContractError("model is required", param="model")

    params: dict[str, Any] = {
        name: data[name]
        for name in UNIFIED_PARAMS
        if name in data and data[name] is not None
    }
    if "duration" in data and data["duration"] is not None:
        duration = _seconds(data["duration"])
        if "seconds" in params and _seconds(params["seconds"]) != duration:
            raise ContractError(
                "seconds and duration are synonyms and must not differ",
                param="seconds",
            )
        params["seconds"] = duration
    if "seconds" in params:
        params["seconds"] = _seconds(params["seconds"])
    if data.get("ratio") is not None and "aspect_ratio" not in params:
        params["aspect_ratio"] = data["ratio"]
    if data.get("size") is not None:
        resolution, aspect_ratio = _size(data["size"])
        params.setdefault("resolution", resolution)
        params.setdefault("aspect_ratio", aspect_ratio)
    if isinstance(params.get("resolution"), str):
        params["resolution"] = params["resolution"].strip().lower()

    raw_references = data.get("references") or []
    if not isinstance(raw_references, list):
        raise ContractError("references must be an array", param="references")
    references = [_reference(item) for item in raw_references]
    references.extend(_legacy_references(data))

    policy = data.get("parameter_policy") or default_policy
    if policy not in {"strict", "adapt"}:
        raise ContractError(
            "parameter_policy must be strict or adapt", param="parameter_policy"
        )

    task = data.get("task")
    legacy_task = data.get("omni_reference_task_type")
    if task is None and isinstance(legacy_task, str) and legacy_task != "auto":
        task = LEGACY_TASKS.get(legacy_task.strip().lower())
    explicit = task is not None
    if task is None:
        task = _infer_task(references, params)
    if task not in TASKS:
        raise ContractError(
            f"Unknown task '{task}'; supported tasks: {', '.join(TASKS)}",
            code="unsupported_task",
            param="task",
        )

    frames_taken = [
        r["role"]
        for r in references
        if r.get("role") in {"first_frame", "last_frame", "base_video"}
    ]
    for reference in references:
        if not reference.get("role"):
            reference["role"] = _default_role(reference, task, frames_taken)

    known = STRUCTURAL_FIELDS.union(UNIFIED_PARAMS)
    extras = {key: value for key, value in data.items() if key not in known}
    provider_options = data.get("provider_options") or {}
    if not isinstance(provider_options, dict):
        raise ContractError(
            "provider_options must be an object", param="provider_options"
        )
    metadata = data.get("metadata") or {}
    return UnifiedRequest(
        model=model.strip(),
        task=task,
        prompt=str(data.get("prompt") or "").strip(),
        references=references,
        params=params,
        provider_options=provider_options,
        policy=policy,
        explicit_task=explicit,
        extras=extras,
        metadata=metadata if isinstance(metadata, dict) else {},
    )
