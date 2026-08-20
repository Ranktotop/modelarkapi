"""Per-model capabilities for the Seedance families offered by ModelArk.

The values mirror the BytePlus "Create a video generation task" reference and
the Dreamina Seedance tutorials. They are the single source of truth for both
model discovery (`GET /v1/models`) and request validation, so a client can ask
the proxy what a model accepts instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

VIDEO_RATIOS = ("adaptive", "16:9", "9:16", "1:1", "4:3", "3:4", "21:9")
VERSION_SUFFIX = re.compile(r"-\d{6}$")

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
    known: bool = True

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
        default_duration=5,
        reference_limits={"image": 30, "video": 10, "audio": 10},
        reference_audio_requires_visual=False,
        reference_media=ReferenceMediaLimits(2, 30, 30),
        output_formats=("mp4", "mov"),
        task_types=TASK_TYPES,
        adaptive_ratio_for_frames=True,
    ),
    "dreamina-seedance-2-0": _SEEDANCE_2_0,
    "dreamina-seedance-2-0-fast": _SEEDANCE_2_0_LIGHT,
    "dreamina-seedance-2-0-mini": _SEEDANCE_2_0_LIGHT,
    "seedance-1-5-pro": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="720p",
        durations=(-1, *range(4, 13)),
        default_duration=5,
    ),
    "seedance-1-0-pro": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="1080p",
        durations=tuple(range(2, 13)),
        default_duration=5,
        default_ratio="16:9",
        supports_frames=True,
    ),
    "seedance-1-0-pro-fast": ModelSpec(
        resolutions=("480p", "720p", "1080p"),
        default_resolution="1080p",
        durations=tuple(range(2, 13)),
        default_duration=5,
        default_ratio="16:9",
        supports_frames=True,
        supports_last_frame_role=False,
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
    """Strip the ``-260628`` style version suffix from a model ID."""
    return VERSION_SUFFIX.sub("", model.removeprefix("openai/").strip())


def spec_for(model: str) -> ModelSpec:
    return MODEL_SPECS.get(family_name(model), FALLBACK_SPEC)


def capabilities_for(model: str) -> dict[str, Any]:
    return spec_for(model).to_capabilities()
