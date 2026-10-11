"""Prompt guide registry, endpoints, and the LiteLLM config export (T8)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.litellm_export import family_slug
from modelark_proxy.prompt_guides import PromptGuides

REPO_GUIDES = Path(__file__).resolve().parents[1] / "prompt_guides"


@pytest.fixture
def guides_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "guides"
    directory.mkdir()
    (directory / "seedance_2_0.md").write_text("# Seedance 2.0 Guide\n\nUse shots.\n")
    (directory / "seedance_2_0_fast.md").write_text("# Fast Guide\n")
    (directory / "manifest.yaml").write_text(
        """
guides:
  - id: seedance_2_0
    file: seedance_2_0.md
    title: Seedance 2.0 Prompting Guide
    language: de
    updated: 2026-08-21
    models: [dreamina-seedance-2-0]
  - id: seedance_2_0_fast
    file: seedance_2_0_fast.md
    title: Seedance 2.0 Fast Guide
    language: de
    updated: 2026-08-21
    models: [dreamina-seedance-2-0-fast]
"""
    )
    return directory


def test_longest_model_prefix_selects_the_guide(guides_dir: Path):
    guides = PromptGuides(guides_dir)

    assert (
        guides.for_model("dreamina-seedance-2-0-fast-260128").id == "seedance_2_0_fast"
    )
    assert guides.for_model("dreamina-seedance-2-0-260128").id == "seedance_2_0"
    assert (
        guides.for_model("openai/dreamina-seedance-2-0-mini-260128").id
        == "seedance_2_0"
    )
    assert guides.for_model("kling-3.0") is None


def test_repository_manifest_matches_the_guide_files():
    guides = PromptGuides(REPO_GUIDES)
    listed = {guide.file for guide in guides.all()}

    assert listed == {path.name for path in REPO_GUIDES.glob("*.md")}
    assert all(guide.markdown().startswith("# ") for guide in guides.all())
    assert guides.for_model("dreamina-seedance-2-5-260628").id == "seedance_2_5"
    assert guides.for_model("veo-3.1-fast-generate-001").id == "veo_3_1"


def test_every_offered_model_has_a_guide():
    from modelark_proxy.models import MODEL_SPECS
    from modelark_proxy.providers import omni, veo
    from modelark_proxy.providers.kling.models import MODELS, VIRTUAL_MODELS

    guides = PromptGuides(REPO_GUIDES)
    # Seedance 1.x is not activated on the account and has no guide.
    seedance = [
        family for family, spec in MODEL_SPECS.items() if not spec.first_generation
    ]
    offered = [*seedance, *veo.LABELS, *omni.LABELS, *MODELS, *VIRTUAL_MODELS]

    assert [model for model in offered if guides.for_model(model) is None] == []
    assert guides.for_model("kling-3.0-turbo").id == "kling_3_0"
    assert guides.for_model("kling-3.0-omni").id == "kling_omni"
    assert guides.for_model("kling-2.5-turbo").id == "kling_2_x"
    assert guides.for_model("kling-video-to-audio").id == "kling_tools"


@pytest.mark.parametrize(
    ("family", "slug"),
    [
        ("dreamina-seedance-2-5", "seedance_25"),
        ("dreamina-seedance-2-0-fast", "seedance_20_fast"),
        ("seedance-1-0-pro", "seedance_10_pro"),
        ("veo-3.1-fast-generate", "veo_31_fast"),
        ("gemini-omni-1.1-flash", "gemini_omni_11_flash"),
        ("kling-3.0-omni", "kling_30_omni"),
        ("kling-lip-sync", "kling_lip_sync"),
    ],
)
def test_family_slugs_follow_the_existing_litellm_names(family: str, slug: str):
    assert family_slug(family) == slug


@pytest.fixture
def settings(tmp_path: Path, guides_dir: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        byteplus_access_key_id="ak-test",
        byteplus_secret_access_key="sk-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://modelark.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        prompt_guides_dir=guides_dir,
    )


def management() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        action = request.url.params["Action"]
        if action == "ListModelActivations":
            items = [
                {
                    "FoundationModelName": "dreamina-seedance-2-0-fast",
                    "DisplayName": "Dreamina-Seedance-2-0-Fast",
                    "State": "Available",
                }
            ]
        else:
            items = [{"ModelVersion": "260128", "Status": "Published"}]
        return httpx.Response(200, json={"Result": {"Items": items, "TotalCount": 1}})

    return httpx.MockTransport(handler)


async def call(settings: Settings, *requests):
    app = create_app(
        settings, asset_transport=management(), validate_startup_credentials=False
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        return [await send(client) for send in requests]


async def test_guides_are_listed_and_served_as_markdown(settings: Settings):
    listing, markdown, as_json, missing, traversal = await call(
        settings,
        lambda c: c.get("/v1/prompt-guides"),
        lambda c: c.get("/v1/prompt-guides/seedance_2_0"),
        lambda c: c.get(
            "/v1/prompt-guides/seedance_2_0", headers={"accept": "application/json"}
        ),
        lambda c: c.get("/v1/prompt-guides/unknown"),
        lambda c: c.get("/v1/prompt-guides/..%2Fmanifest.yaml"),
    )

    assert [guide["id"] for guide in listing.json()["data"]] == [
        "seedance_2_0",
        "seedance_2_0_fast",
    ]
    assert listing.json()["data"][0]["url"] == "/v1/prompt-guides/seedance_2_0"
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("# Seedance 2.0 Guide")
    assert as_json.json()["markdown"].startswith("# Seedance 2.0 Guide")
    assert as_json.json()["title"] == "Seedance 2.0 Prompting Guide"
    assert missing.status_code == 404
    assert traversal.status_code == 404


async def test_models_link_their_guide_and_single_model_embeds_it(settings: Settings):
    listing, single, missing = await call(
        settings,
        lambda c: c.get("/v1/models"),
        lambda c: c.get("/v1/models/dreamina-seedance-2-0-fast-260128"),
        lambda c: c.get("/v1/models/unknown-model"),
    )

    model = listing.json()["data"][0]
    assert model["links"] == {"prompt_guide": "/v1/prompt-guides/seedance_2_0_fast"}
    assert "prompt_guide" not in model
    assert single.json()["id"] == "dreamina-seedance-2-0-fast-260128"
    assert single.json()["prompt_guide"]["markdown"] == "# Fast Guide\n"
    assert single.json()["prompt_guide"]["id"] == "seedance_2_0_fast"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "model_unavailable"


async def test_litellm_export_carries_capabilities_and_guide_text(settings: Settings):
    as_yaml, as_json = await call(
        settings,
        lambda c: c.get("/v1/litellm/config"),
        lambda c: c.get(
            "/v1/litellm/config",
            params={
                "format": "json",
                "api_base": "http://modelarkapi_server:8080/v1",
                "name_template": "{model}",
            },
        ),
    )

    exported = yaml.safe_load(as_yaml.text)
    entry = exported["model_list"][0]
    assert as_yaml.headers["content-type"].startswith("application/yaml")
    assert entry["model_name"] == "seedance_20_fast_api"
    assert entry["litellm_params"] == {
        "model": "openai/dreamina-seedance-2-0-fast-260128",
        "api_base": "https://modelark.example.com/v1",
        "api_key": "os.environ/MODELARK_PROXY_API_KEY",
    }
    info = entry["model_info"]
    assert info["mode"] == "video_generation"
    assert info["provider"] == "modelark"
    assert info["prompt_guide"] == "# Fast Guide\n"
    assert info["prompt_guide_url"] == (
        "https://modelark.example.com/v1/prompt-guides/seedance_2_0_fast"
    )
    assert info["capabilities"]["schema_version"] == 2

    json_entry = as_json.json()["model_list"][0]
    assert json_entry["model_name"] == "dreamina-seedance-2-0-fast-260128"
    assert (
        json_entry["litellm_params"]["api_base"] == "http://modelarkapi_server:8080/v1"
    )
