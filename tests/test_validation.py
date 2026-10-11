"""Capability schema v2, unified request normalization, and validation (T7a)."""

from __future__ import annotations

import pytest

from modelark_proxy.capabilities import (
    Constraint,
    GroupLimit,
    ModelCapabilities,
    Param,
    ReferenceSlot,
    TaskSpec,
)
from modelark_proxy.models import capabilities_for
from modelark_proxy.unified import normalize_request
from modelark_proxy.validation import ContractError, validate

VEO_LIKE = ModelCapabilities(
    provider="google",
    family="veo-3.1-fast",
    prompt_max_chars=4000,
    max_outputs=4,
    parameters={
        "seconds": Param(values=(4, 6, 8), default=8),
        "resolution": Param(values=("720p", "1080p"), default="720p"),
        "aspect_ratio": Param(values=("16:9", "9:16"), default="16:9"),
        "seed": Param(minimum=0, maximum=4_294_967_295),
        "negative_prompt": Param(),
        "generate_audio": Param(default=True),
        "n": Param(minimum=1, maximum=4, default=1),
    },
    tasks={
        "text_to_video": TaskSpec(),
        "image_to_video": TaskSpec(
            references=(ReferenceSlot("first_frame", ("image",), 1, 1),)
        ),
        "reference_to_video": TaskSpec(
            references=(ReferenceSlot("reference", ("image",), 1, 3),),
            parameters={"seconds": Param(values=(8,), default=8)},
        ),
    },
    constraints=(
        Constraint(
            when={"resolution": ("1080p",)},
            then={"seconds": (8,)},
            message="1080p requires 8 seconds",
        ),
    ),
)


def check(data: dict, caps: ModelCapabilities = VEO_LIKE, policy: str = "strict"):
    return validate(caps, normalize_request(data), policy)


# --- normalization and task inference -------------------------------------


@pytest.mark.parametrize(
    ("data", "task"),
    [
        ({"prompt": "fox"}, "text_to_video"),
        (
            {"references": [{"type": "image", "url": "https://e/a.png"}]},
            "image_to_video",
        ),
        (
            {
                "references": [
                    {"type": "image", "url": "https://e/a.png", "role": "first_frame"},
                    {"type": "image", "url": "https://e/b.png", "role": "last_frame"},
                ]
            },
            "first_last_frame",
        ),
        (
            {
                "references": [
                    {"type": "image", "url": "https://e/a.png"},
                    {"type": "image", "url": "https://e/b.png"},
                ]
            },
            "reference_to_video",
        ),
        (
            {
                "references": [
                    {"type": "video", "url": "https://e/a.mp4", "role": "base_video"}
                ]
            },
            "edit",
        ),
        (
            {
                "references": [{"task_id": "cgt-1", "role": "base_video"}],
                "speech": {"text": "hi"},
            },
            "lip_sync",
        ),
        (
            {
                "references": [
                    {"type": "video", "url": "https://e/m.mp4", "role": "motion"}
                ]
            },
            "motion_control",
        ),
        ({"effect": "hug_pro"}, "effect"),
        ({"shots": [{"prompt": "a", "seconds": 2}]}, "multi_shot"),
        ({"prompt": "x", "task": "extend"}, "extend"),
    ],
)
def test_task_is_inferred_as_specified(data: dict, task: str):
    assert normalize_request({"model": "m", **data}).task == task


def test_role_defaults_follow_the_task():
    request = normalize_request(
        {"model": "m", "references": [{"type": "image", "url": "https://e/a.png"}]}
    )

    assert request.references[0]["role"] == "first_frame"


def test_seconds_and_duration_are_synonyms_but_must_agree():
    assert normalize_request({"model": "m", "duration": "6"}).params["seconds"] == 6
    with pytest.raises(ContractError) as error:
        normalize_request({"model": "m", "seconds": 4, "duration": 6})
    assert error.value.code == "invalid_request"


def test_size_translates_to_resolution_and_aspect_ratio():
    params = normalize_request({"model": "m", "size": "720x1280"}).params

    assert params["resolution"] == "720p"
    assert params["aspect_ratio"] == "9:16"


def test_explicit_resolution_wins_over_size_and_ratio_is_an_alias():
    params = normalize_request(
        {"model": "m", "size": "1280x720", "resolution": "1080p", "ratio": "9:16"}
    ).params

    assert params["resolution"] == "1080p"
    assert params["aspect_ratio"] == "9:16"


def test_legacy_seedance_reference_fields_become_references():
    request = normalize_request(
        {
            "model": "m",
            "input_reference_url": "https://e/a.png",
            "input_reference_media_type": "image",
            "reference_urls": [
                "https://e/b.png",
                {
                    "url": "https://e/c.mp4",
                    "media_type": "video",
                    "role": "reference_video",
                },
            ],
        }
    )

    assert [(r["type"], r.get("url")) for r in request.references] == [
        ("image", "https://e/a.png"),
        ("image", "https://e/b.png"),
        ("video", "https://e/c.mp4"),
    ]
    assert request.references[2]["role"] == "reference"


def test_each_reference_needs_exactly_one_source():
    with pytest.raises(ContractError) as error:
        normalize_request(
            {
                "model": "m",
                "references": [
                    {"type": "image", "url": "https://e/a.png", "upload_id": "ref-1"}
                ],
            }
        )
    assert error.value.code == "invalid_request"


# --- strict validation -----------------------------------------------------


def test_valid_request_passes_and_receives_forced_values():
    request, adjustments = check(
        {
            "model": "m",
            "prompt": "fox",
            "references": [{"type": "image", "url": "https://e/a.png"}] * 2,
        }
    )

    assert request.task == "reference_to_video"
    assert request.params["seconds"] == 8
    assert adjustments == []


def test_unsupported_task_is_rejected():
    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "task": "lip_sync"})
    assert error.value.code == "unsupported_task"
    assert "text_to_video" in str(error.value)


def test_unsupported_value_lists_allowed_values():
    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "seconds": 5})
    assert error.value.code == "unsupported_parameter"
    assert error.value.param == "seconds"
    assert "4, 6, 8" in str(error.value)


def test_task_specific_parameters_narrow_the_model_values():
    with pytest.raises(ContractError) as error:
        check(
            {
                "model": "m",
                "prompt": "x",
                "seconds": 4,
                "references": [{"type": "image", "url": "https://e/a.png"}] * 2,
            }
        )
    assert error.value.code == "unsupported_parameter"


def test_constraints_reject_conflicting_combinations():
    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "resolution": "1080p", "seconds": 4})
    assert "1080p requires 8 seconds" in str(error.value)


def test_constraints_fill_unset_values():
    request, _ = check({"model": "m", "prompt": "x", "resolution": "1080p"})

    assert request.params["seconds"] == 8


def test_parameters_the_model_lacks_are_rejected():
    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "quality": "pro"})
    assert error.value.code == "unsupported_parameter"
    assert error.value.param == "quality"


def test_unknown_fields_are_rejected():
    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "frames": 121})
    assert error.value.code == "unsupported_parameter"


def test_reference_counts_are_enforced():
    with pytest.raises(ContractError) as error:
        check(
            {
                "model": "m",
                "prompt": "x",
                "references": [{"type": "image", "url": "https://e/a.png"}] * 4,
            }
        )
    assert error.value.code == "reference_limit"


def test_reference_types_are_enforced():
    with pytest.raises(ContractError) as error:
        check(
            {
                "model": "m",
                "prompt": "x",
                "task": "reference_to_video",
                "references": [{"type": "audio", "url": "https://e/a.mp3"}],
            }
        )
    assert error.value.code == "reference_limit"


def test_group_limits_are_enforced():
    caps = ModelCapabilities(
        provider="kling",
        family="kling-3.0-omni",
        parameters={},
        tasks={
            "reference_to_video": TaskSpec(
                references=(
                    ReferenceSlot("reference", ("image", "element", "video"), 1, 10),
                ),
                limits=(
                    GroupLimit(
                        roles=("reference",),
                        types=("image", "element"),
                        maximum=4,
                        when_has=("video",),
                    ),
                ),
            )
        },
    )
    references = [{"type": "image", "url": "https://e/a.png"}] * 5 + [
        {"type": "video", "url": "https://e/v.mp4"}
    ]

    with pytest.raises(ContractError) as error:
        check({"model": "m", "prompt": "x", "references": references}, caps)
    assert error.value.code == "reference_limit"


# --- adapt policy ----------------------------------------------------------


def test_adapt_snaps_to_the_nearest_allowed_value_and_records_it():
    request, adjustments = check(
        {"model": "m", "prompt": "x", "seconds": 5, "resolution": "360p"},
        policy="adapt",
    )

    assert request.params["seconds"] == 6
    assert request.params["resolution"] == "720p"
    assert {a["field"] for a in adjustments} == {"seconds", "resolution"}


def test_adapt_applies_constraints_after_snapping():
    request, _ = check(
        {"model": "m", "prompt": "x", "seconds": 5, "resolution": "4k"}, policy="adapt"
    )

    assert request.params["resolution"] == "1080p"
    assert request.params["seconds"] == 8


def test_adapt_drops_unsupported_optional_fields():
    request, adjustments = check(
        {"model": "m", "prompt": "x", "quality": "pro", "frames": 121}, policy="adapt"
    )

    assert "quality" not in request.params
    assert {a["field"] for a in adjustments} == {"quality", "frames"}


def test_adapt_still_rejects_missing_inputs():
    with pytest.raises(ContractError):
        check({"model": "m", "prompt": "x", "task": "image_to_video"}, policy="adapt")


def test_policy_can_be_requested_per_call():
    request = normalize_request({"model": "m", "parameter_policy": "adapt"})

    assert request.policy == "adapt"


# --- capability documents --------------------------------------------------


def test_seedance_capabilities_keep_v1_and_add_v2():
    caps = capabilities_for("dreamina-seedance-2-5-260628")

    assert caps["resolutions"] == ["480p", "720p", "1080p"]
    assert caps["schema_version"] == 2
    assert caps["provider"] == "modelark"
    assert caps["parameters"]["seconds"]["values"][0] == "auto"
    assert set(caps["tasks"]) >= {
        "text_to_video",
        "image_to_video",
        "first_last_frame",
        "reference_to_video",
        "edit",
        "extend",
        "stitch",
    }
    assert caps["features"]["real_human"] is True
    assert caps["continuation"] == "last_frame"


def test_seedance_1_0_pro_fast_has_no_last_frame_or_references():
    caps = capabilities_for("seedance-1-0-pro-fast-251015")

    assert "first_last_frame" not in caps["tasks"]
    assert "reference_to_video" not in caps["tasks"]
    assert "image_to_video" in caps["tasks"]


def test_capability_document_serializes_constraints():
    document = VEO_LIKE.to_dict()

    assert document["constraints"] == [
        {
            "if": {"resolution": ["1080p"]},
            "then": {"seconds": [8]},
            "message": "1080p requires 8 seconds",
        }
    ]
    assert document["tasks"]["image_to_video"]["references"][0] == {
        "role": "first_frame",
        "types": ["image"],
        "min": 1,
        "max": 1,
    }


# --- the v2 document must describe what Seedance really enforces -----------

SEEDANCE_CASES = [
    ("dreamina-seedance-2-5-260628", {"prompt": "x", "duration": 30}),
    ("dreamina-seedance-2-5-260628", {"prompt": "x", "duration": 31}),
    ("dreamina-seedance-2-0-fast-260128", {"prompt": "x", "resolution": "1080p"}),
    ("dreamina-seedance-2-0-260128", {"prompt": "x", "resolution": "4k"}),
    ("dreamina-seedance-2-0-260128", {"prompt": "x", "ratio": "5:4"}),
    (
        "seedance-1-0-pro-fast-251015",
        {
            "prompt": "x",
            "reference_urls": [
                {
                    "url": "https://e/a.png",
                    "media_type": "image",
                    "role": "first_frame",
                },
                {"url": "https://e/b.png", "media_type": "image", "role": "last_frame"},
            ],
        },
    ),
    (
        "seedance-1-5-pro-251215",
        {
            "prompt": "x",
            "reference_urls": [{"url": "https://e/a.png", "media_type": "image"}] * 2,
        },
    ),
    (
        "dreamina-seedance-2-0-260128",
        {
            "prompt": "x",
            "reference_urls": [{"url": "https://e/a.png", "media_type": "image"}] * 10,
        },
    ),
    (
        "dreamina-seedance-2-0-260128",
        {
            "prompt": "x",
            "reference_urls": [{"url": "https://e/a.mp3", "media_type": "audio"}],
        },
    ),
    (
        "dreamina-seedance-2-5-260628",
        {
            "prompt": "x",
            "reference_urls": [{"url": "https://e/a.mp3", "media_type": "audio"}],
        },
    ),
    (
        "dreamina-seedance-2-5-260628",
        {
            "prompt": "x",
            "omni_reference_task_type": "edit",
            "ratio": "16:9",
            "reference_urls": [{"url": "https://e/a.mp4", "media_type": "video"}],
        },
    ),
    (
        "dreamina-seedance-2-5-260628",
        {
            "prompt": "x",
            "omni_reference_task_type": "edit",
            "reference_urls": [{"url": "https://e/a.mp4", "media_type": "video"}],
        },
    ),
    (
        "dreamina-seedance-2-5-260628",
        {
            "prompt": "x",
            "ratio": "16:9",
            "reference_urls": [
                {"url": "https://e/a.png", "media_type": "image", "role": "first_frame"}
            ],
        },
    ),
]


@pytest.mark.parametrize(("model", "body"), SEEDANCE_CASES)
def test_seedance_v2_document_agrees_with_seedance_validation(model, body, tmp_path):
    from modelark_proxy.config import Settings
    from modelark_proxy.models import seedance_capabilities
    from modelark_proxy.providers.seedance import build_task_payload
    from modelark_proxy.translation import TranslationError

    data = {"model": model, **body}
    try:
        build_task_payload(dict(data), Settings(), None)
        seedance_accepts = True
    except TranslationError:
        seedance_accepts = False
    try:
        validate(seedance_capabilities(model), normalize_request(dict(data)))
        engine_accepts = True
    except ContractError:
        engine_accepts = False

    assert engine_accepts == seedance_accepts
