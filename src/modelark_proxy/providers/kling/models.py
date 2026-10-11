"""Kling model catalogue and capabilities (tasks/research/kling.md, section 3)."""

from __future__ import annotations

from dataclasses import dataclass

from ...capabilities import (
    Constraint,
    ModelCapabilities,
    Param,
    ReferenceSlot,
    TaskSpec,
)

IMAGE_FORMATS = ("image/jpeg", "image/png")
# Legacy endpoints accept images up to 10 MB, the new API up to 50 MB.
LEGACY_IMAGE_BYTES = 10 * 1024 * 1024
NEW_IMAGE_BYTES = 50 * 1024 * 1024
RESOLUTION_MODES = {"720p": "std", "1080p": "pro", "4k": "4k"}
QUALITY_RESOLUTIONS = {"standard": "720p", "pro": "1080p"}
TEXT_RATIOS = ("16:9", "9:16", "1:1")


@dataclass(frozen=True)
class KlingModel:
    id: str
    label: str
    # Legacy `model_name`; None means the model only exists in the new API.
    legacy_name: str | None
    seconds: tuple[int, ...]
    resolutions: tuple[str, ...]
    audio: bool = False
    audio_needs_1080p: bool = False
    first_last: bool = True
    first_last_needs_1080p: bool = False
    multi_shot: bool = False
    elements: bool = False
    voices: bool = False


MODELS: dict[str, KlingModel] = {
    model.id: model
    for model in (
        KlingModel(
            "kling-3.0-turbo",
            "Kling 3.0 Turbo",
            None,
            tuple(range(3, 16)),
            ("720p", "1080p"),
            first_last=False,
            multi_shot=True,
        ),
        KlingModel(
            "kling-3.0",
            "Kling 3.0",
            "kling-v3",
            tuple(range(3, 16)),
            ("720p", "1080p", "4k"),
            audio=True,
            multi_shot=True,
            elements=True,
        ),
        KlingModel(
            "kling-2.6",
            "Kling 2.6",
            "kling-v2-6",
            (5, 10),
            ("720p", "1080p"),
            audio=True,
            audio_needs_1080p=True,
            first_last_needs_1080p=True,
            voices=True,
        ),
        KlingModel(
            "kling-2.5-turbo",
            "Kling 2.5 Turbo",
            "kling-v2-5-turbo",
            (5, 10),
            ("720p", "1080p"),
            first_last_needs_1080p=True,
        ),
    )
}
ALIASES = {
    model.legacy_name: model.id for model in MODELS.values() if model.legacy_name
}


def canonical_model(model: str) -> str | None:
    model = ALIASES.get(model, model)
    return model if model in MODELS else None


def kling_capabilities(model_id: str) -> ModelCapabilities:
    model = MODELS[model_id]
    legacy = model.legacy_name is not None
    image_bytes = LEGACY_IMAGE_BYTES if legacy else NEW_IMAGE_BYTES

    def frame(role: str, minimum: int = 1) -> ReferenceSlot:
        return ReferenceSlot(
            role, ("image",), minimum, 1, max_bytes=image_bytes, formats=IMAGE_FORMATS
        )

    parameters: dict[str, Param] = {
        "seconds": Param(values=model.seconds, default=5),
        "resolution": Param(values=model.resolutions, default="720p"),
        # Image-based tasks take the aspect ratio from the image ("adaptive").
        "aspect_ratio": Param(values=(*TEXT_RATIOS, "adaptive"), default="16:9"),
        "quality": Param(values=tuple(QUALITY_RESOLUTIONS)),
        "watermark": Param(default=False),
    }
    if legacy:
        parameters["negative_prompt"] = Param()
    if model.audio:
        parameters["generate_audio"] = Param(default=False)
    tasks: dict[str, TaskSpec] = {
        "text_to_video": TaskSpec(),
        "image_to_video": TaskSpec(
            references=(frame("first_frame"),), prompt_required=False
        ),
    }
    if model.first_last:
        tasks["first_last_frame"] = TaskSpec(
            references=(frame("first_frame"), frame("last_frame")),
            prompt_required=False,
        )
    if model.multi_shot:
        parameters["shot_mode"] = Param(
            values=("customize", "intelligence"), default="customize"
        )
        parameters["shots"] = Param()
        tasks["multi_shot"] = TaskSpec(
            references=(frame("first_frame", 0),) if legacy else (),
            prompt_required=False,
        )
    constraints = [
        Constraint(
            when={"task": ("text_to_video", "multi_shot")},
            then={"aspect_ratio": TEXT_RATIOS},
            message="Text-based Kling tasks support 16:9, 9:16 and 1:1",
        ),
        Constraint(
            when={"task": ("image_to_video", "first_last_frame")},
            then={"aspect_ratio": ("adaptive",)},
            message="Kling takes the aspect ratio from the input image",
        ),
    ]
    if model.audio_needs_1080p:
        constraints.append(
            Constraint(
                when={"generate_audio": (True,)},
                then={"resolution": ("1080p",)},
                message=f"{model.label} generates native audio only at 1080p",
            )
        )
    if model.first_last_needs_1080p:
        then: dict[str, tuple[object, ...]] = {"resolution": ("1080p",)}
        if model.audio:
            then["generate_audio"] = (False,)
        constraints.append(
            Constraint(
                when={"task": ("first_last_frame",)},
                then=then,
                message=f"{model.label} renders first and last frames only at 1080p without audio",
            )
        )
    return ModelCapabilities(
        provider="kling",
        family=model.id,
        launch_stage="ga",
        prompt_max_chars=2500 if legacy else 3072,
        parameters=parameters,
        tasks=tasks,
        constraints=tuple(constraints),
        features={"watermark": True},
    )
