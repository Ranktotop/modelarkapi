"""Per-model capabilities for the Seedance families offered by ModelArk.

The values mirror the BytePlus "Create a video generation task" reference and
the Dreamina Seedance tutorials. They are the single source of truth for both
model discovery (`GET /v1/models`) and request validation, so a client can ask
the proxy what a model accepts instead of guessing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .capabilities import (
    Constraint,
    GroupLimit,
    ModelCapabilities,
    Param,
    ReferenceSlot,
    TaskSpec,
)

logger = logging.getLogger(__name__)

VIDEO_RATIOS = ("adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9")
# ModelArk appends a release date to every model ID: `-260628`, `-251215`,
# and in older listings the four-digit or full-date spellings. Capabilities
# belong to the family, so a new revision of a known model keeps working.
VERSION_SUFFIX = re.compile(r"-\d{4,10}$")
_unknown_families: set[str] = set()

# Task hints accepted by `omni_reference_task_type` (Seedance 2.5 only).
TASK_TYPES = ("auto", "reference", "edit", "extend")
# Subtasks whose aspect ratio is dictated by the input asset.
ADAPTIVE_RATIO_TASKS = ("edit", "extend")


@dataclass(frozen=True)
class ReferenceMediaLimits:
    """Duration limits for reference video and audio assets, in seconds."""

    min_seconds: int
    max_seconds: int
    total_seconds: int


@dataclass(frozen=True)
class ModelSpec:
    resolutions: tuple[str, ...]
    default_resolution: str
    durations: tuple[int, ...]
    default_duration: int
    default_ratio: str = "adaptive"
    ratios: tuple[str, ...] = VIDEO_RATIOS
    reference_limits: dict[str, int] = field(
        default_factory=lambda: {"image": 0, "video": 0, "audio": 0}
    )
    reference_audio_requires_visual: bool = True
    reference_media: ReferenceMediaLimits | None = None
    output_formats: tuple[str, ...] = ("mp4",)
    task_types: tuple[str, ...] = ()
    supports_frames: bool = False
    supports_last_frame_role: bool = True
    adaptive_ratio_for_frames: bool = False
    # `generate_audio` is rejected by models without audio output (1.0 pro).
    supports_audio: bool = True
    # Draft mode: a 480p preview first, then the final video from its task ID.
    supports_draft: bool = False
    # Seedance 1.x: camera_fixed, service_tier=flex, no priority, and (1.0)
    # no adaptive ratio without an input image.
    first_generation: bool = False
    adaptive_needs_image: bool = False
    # Shortest video an edit accepts, when it differs from reference_media.
    edit_min_seconds: int | None = None
    deprecation: tuple[str, str] | None = None
    known: bool = True
    provider: str = "modelark"

    @property
    def supports_references(self) -> bool:
        return any(self.reference_limits.values())

    def to_capabilities(self) -> dict[str, Any]:
        """Public capability document exposed through the API."""
        capabilities: dict[str, Any] = {
            "resolutions": list(self.resolutions),
            "ratios": list(self.ratios),
            "durations": list(self.durations),
            "defaults": {
                "resolution": self.default_resolution,
                "ratio": self.default_ratio,
                "duration": self.default_duration,
            },
            "reference_limits": dict(self.reference_limits),
            "reference_audio_requires_visual": self.reference_audio_requires_visual,
            "output_formats": list(self.output_formats),
            "task_types": list(self.task_types),
            "supports_frames": self.supports_frames,
            "supports_last_frame_role": self.supports_last_frame_role,
            "adaptive_ratio_for_frames": self.adaptive_ratio_for_frames,
        }
        if self.reference_media:
            capabilities["reference_media_seconds"] = {
                "min": self.reference_media.min_seconds,
                "max": self.reference_media.max_seconds,
                "total": self.reference_media.total_seconds,
            }
        return capabilities


_SEEDANCE_2_0 = ModelSpec(
    resolutions=("480p", "720p", "1080p", "4k"),
    default_resolution="720p",
    durations=(-1, *range(4, 16)),
    default_duration=5,
    reference_limits={"image": 9, "video": 3, "audio": 3},
    reference_media=ReferenceMediaLimits(2, 15, 15),
)
_SEEDANCE_2_0_LIGHT = ModelSpec(
    resolutions=("480p", "720p"),
    default_resolution="720p",
    durations=(-1, *range(4, 16)),
    default_duration=5,
    reference_limits={"image": 9, "video": 3, "audio": 3},
    reference_media=ReferenceMediaLimits(2, 15, 15),
)

MODEL_SPECS: dict[str, ModelSpec] = {
    "dreamina-seedance-2-5": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="720p",
        durations=(-1, *range(4, 31)),
        default_duration=-1,
        reference_limits={"image": 30, "video": 10, "audio": 10},
        reference_audio_requires_visual=False,
        reference_media=ReferenceMediaLimits(2, 30, 30),
        output_formats=("mp4", "mov"),
        task_types=TASK_TYPES,
        adaptive_ratio_for_frames=True,
        supports_draft=True,
        edit_min_seconds=4,
    ),
    "dreamina-seedance-2-0": _SEEDANCE_2_0,
    "dreamina-seedance-2-0-fast": _SEEDANCE_2_0_LIGHT,
    "dreamina-seedance-2-0-mini": _SEEDANCE_2_0_LIGHT,
    "seedance-1-5-pro": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="720p",
        durations=(-1, *range(4, 13)),
        default_duration=5,
        supports_draft=True,
        first_generation=True,
        # Retired by BytePlus; shutdown 2026-11-11 17:00 UTC+8.
        deprecation=("2026-11-11T09:00:00Z", "dreamina-seedance-2-0-mini"),
    ),
    "seedance-1-0-pro": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="1080p",
        durations=tuple(range(2, 13)),
        default_duration=5,
        default_ratio="16:9",
        supports_frames=True,
        supports_audio=False,
        first_generation=True,
        adaptive_needs_image=True,
    ),
    "seedance-1-0-pro-fast": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="1080p",
        durations=tuple(range(2, 13)),
        default_duration=5,
        default_ratio="16:9",
        supports_frames=True,
        supports_last_frame_role=False,
        supports_audio=False,
        first_generation=True,
        adaptive_needs_image=True,
    ),
}

# Used for models ModelArk activates before this table knows about them. It
# stays permissive on purpose: unknown models are validated upstream instead of
# being rejected here.
FALLBACK_SPEC = ModelSpec(
    resolutions=("480p", "720p", "1080p"),
    default_resolution="720p",
    durations=(-1, *range(4, 16)),
    default_duration=5,
    reference_limits={"image": 9, "video": 3, "audio": 3},
    known=False,
)


def family_name(model: str) -> str:
    """Reduce a model ID to its family, dropping the release-date suffix.

    ``dreamina-seedance-2-5-260628`` and any later revision of it both resolve
    to ``dreamina-seedance-2-5``; variants such as ``…-2-5-fast`` stay separate
    families because their limits differ.
    """
    return VERSION_SUFFIX.sub("", model.removeprefix("openai/").strip())


def spec_for(model: str) -> ModelSpec:
    family = family_name(model)
    spec = MODEL_SPECS.get(family)
    if spec:
        return spec
    if family and family not in _unknown_families:
        _unknown_families.add(family)
        logger.warning(
            "No capability profile for model family %r; leaving its parameter "
            "validation to ModelArk",
            family,
        )
    return FALLBACK_SPEC


# Seedance fields accepted as-is next to the unified parameters (SPEC 17).
SEEDANCE_NATIVE_FIELDS = (
    "service_tier",
    "execution_expires_after",
    "safety_identifier",
    "callback_url",
    "content",
    "input_reference_task_id",
    "draft",
    "draft_task_id",
)


def seedance_capabilities(model: str) -> ModelCapabilities:
    """Capability document v2 derived from the Seedance ModelSpec."""
    spec = spec_for(model)
    durations = tuple("auto" if value == -1 else value for value in spec.durations)
    default_seconds = "auto" if spec.default_duration == -1 else spec.default_duration
    parameters: dict[str, Param] = {
        "seconds": Param(values=durations, default=default_seconds),
        "resolution": Param(values=spec.resolutions, default=spec.default_resolution),
        "aspect_ratio": Param(values=spec.ratios, default=spec.default_ratio),
        "seed": Param(minimum=-1, maximum=2_147_483_647),
        "watermark": Param(default=False),
        "return_last_frame": Param(default=False),
    }
    if spec.supports_audio:
        parameters["generate_audio"] = Param(default=True)
    if len(spec.output_formats) > 1:
        parameters["output_format"] = Param(
            values=spec.output_formats, default=spec.output_formats[0]
        )
    media = spec.reference_media
    timing = (
        {
            "min_seconds": media.min_seconds,
            "max_seconds": media.max_seconds,
            "total_max_seconds": media.total_seconds,
        }
        if media
        else {}
    )
    first_frame = ReferenceSlot("first_frame", ("image",), 1, 1)
    tasks: dict[str, TaskSpec] = {
        "text_to_video": TaskSpec(),
        "image_to_video": TaskSpec(references=(first_frame,), prompt_required=False),
    }
    if spec.supports_last_frame_role:
        tasks["first_last_frame"] = TaskSpec(
            references=(first_frame, ReferenceSlot("last_frame", ("image",), 1, 1)),
            prompt_required=False,
        )
    limits = spec.reference_limits
    if spec.supports_references:
        kinds = tuple(kind for kind in ("image", "video", "audio") if limits[kind])
        per_kind = tuple(
            GroupLimit(roles=("reference",), types=(kind,), maximum=limits[kind])
            for kind in kinds
        )
        audio_needs_visual = (
            (
                GroupLimit(
                    roles=("reference",),
                    types=("audio",),
                    maximum=0,
                    when_lacks=("image", "video"),
                ),
            )
            if spec.reference_audio_requires_visual
            else ()
        )
        tasks["reference_to_video"] = TaskSpec(
            references=(
                ReferenceSlot("reference", kinds, 1, sum(limits.values()), **timing),
            ),
            limits=per_kind + audio_needs_visual,
        )
        if limits["video"]:
            base_video = ReferenceSlot("base_video", ("video",), 1, 1, **timing)
            edit_video = (
                ReferenceSlot(
                    "base_video",
                    ("video",),
                    1,
                    1,
                    **(timing | {"min_seconds": spec.edit_min_seconds}),
                )
                if spec.edit_min_seconds
                else base_video
            )
            extra = ReferenceSlot(
                "reference", kinds, 0, sum(limits.values()) - 1, **timing
            )
            tasks["edit"] = TaskSpec(references=(edit_video, extra), limits=per_kind)
            tasks["extend"] = TaskSpec(references=(base_video, extra), limits=per_kind)
        if limits["video"] >= 2:
            tasks["stitch"] = TaskSpec(
                references=(
                    ReferenceSlot(
                        "reference", ("video",), 2, limits["video"], **timing
                    ),
                )
            )
    constraints: list[Constraint] = []
    if spec.adaptive_ratio_for_frames:
        constraints.append(
            Constraint(
                when={"task": ("image_to_video", "first_last_frame")},
                then={"aspect_ratio": ("adaptive",)},
                message="First/last-frame generation keeps the input aspect ratio",
            )
        )
    if "edit" in spec.task_types:
        constraints.append(
            Constraint(
                when={"task": ("edit",)},
                then={"aspect_ratio": ("adaptive",), "seconds": ("auto",)},
                message="Editing keeps the aspect ratio and duration of the input video",
            )
        )
    if "extend" in spec.task_types:
        constraints.append(
            Constraint(
                when={"task": ("extend",)},
                then={"aspect_ratio": ("adaptive",)},
                message="Extending keeps the aspect ratio of the input video",
            )
        )
    return ModelCapabilities(
        provider=spec.provider,
        family=family_name(model),
        parameters=parameters,
        tasks=tasks,
        constraints=tuple(constraints),
        continuation="last_frame",
        features={
            "real_human": True,
            "last_frame_output": True,
            "watermark": True,
            "callback": True,
            "draft": spec.supports_draft,
        },
        native_fields=SEEDANCE_NATIVE_FIELDS
        + (("frames",) if spec.supports_frames else ())
        + (("camera_fixed",) if spec.first_generation else ("priority",)),
        launch_stage="deprecated" if spec.deprecation else None,
        deprecation=(
            {"shutdown_at": spec.deprecation[0], "replacement": spec.deprecation[1]}
            if spec.deprecation
            else None
        ),
    )


def capabilities_for(model: str) -> dict[str, Any]:
    """v1 fields (kept for existing clients) plus the v2 document."""
    return spec_for(model).to_capabilities() | seedance_capabilities(model).to_dict()
