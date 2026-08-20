from __future__ import annotations

import pytest

from modelark_proxy.models import (
    FALLBACK_SPEC,
    MODEL_SPECS,
    capabilities_for,
    family_name,
    spec_for,
)


@pytest.mark.parametrize(
    ("model", "family"),
    [
        ("dreamina-seedance-2-5-260628", "dreamina-seedance-2-5"),
        # A later revision of the same model must resolve identically.
        ("dreamina-seedance-2-5-271231", "dreamina-seedance-2-5"),
        ("dreamina-seedance-2-5-20271231", "dreamina-seedance-2-5"),
        ("openai/dreamina-seedance-2-5-260628", "dreamina-seedance-2-5"),
        ("dreamina-seedance-2-5", "dreamina-seedance-2-5"),
        ("dreamina-seedance-2-0-fast-260128", "dreamina-seedance-2-0-fast"),
        ("seedance-1-5-pro-251215", "seedance-1-5-pro"),
    ],
)
def test_model_ids_resolve_to_their_family(model: str, family: str):
    assert family_name(model) == family
    assert spec_for(model) is MODEL_SPECS[family]


def test_future_revisions_keep_the_full_capability_set():
    current = capabilities_for("dreamina-seedance-2-5-260628")
    future = capabilities_for("dreamina-seedance-2-5-280101")

    assert future == current
    assert future["resolutions"] == ["480p", "720p", "1080p"]
    assert future["durations"][-1] == 30
    assert future["reference_limits"] == {"image": 30, "video": 10, "audio": 10}


def test_variants_do_not_inherit_the_base_model_profile():
    """A `-fast`/`-mini` variant is its own family with its own limits."""
    assert spec_for("dreamina-seedance-2-0-fast-260128").resolutions == (
        "480p",
        "720p",
    )
    # An unknown variant stays permissive instead of borrowing 2.5's limits.
    assert spec_for("dreamina-seedance-2-5-fast-270101") is FALLBACK_SPEC


def test_unknown_models_fall_back_without_local_limits():
    spec = spec_for("dreamina-seedance-3-0-270601")

    assert spec is FALLBACK_SPEC
    assert spec.known is False
