"""LiteLLM wire compatibility: request encodings and LiteLLM-style video IDs."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest

from modelark_proxy.app import create_app, form_to_data
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_video_id, encode_video_id


def litellm_decode(video_id: str) -> dict[str, str]:
    """Mirror of litellm.types.videos.utils.decode_video_id_with_provider."""
    cleaned = video_id.replace("video_", "")
    cleaned += "=" * (-len(cleaned) % 4)
    decoded = base64.b64decode(cleaned.encode()).decode()
    provider, model, original = decoded.split(";")[:3]
    return {
        "provider": provider.replace("litellm:custom_llm_provider:", ""),
        "model_id": model.replace("model_id:", ""),
        "video_id": original.replace("video_id:", ""),
    }


def test_encoded_id_is_readable_by_litellm():
    encoded = encode_video_id("cgt-123", "dreamina-seedance-2-5-260628")

    assert encoded.startswith("video_")
    assert litellm_decode(encoded) == {
        "provider": "openai",
        "model_id": "dreamina-seedance-2-5-260628",
        "video_id": "cgt-123",
    }


def test_encoded_id_is_path_safe():
    encoded = encode_video_id(
        "vid-veo-0123456789abcdef0123456789abcdef", "veo-3.1-fast-generate-001"
    )

    assert "/" not in encoded and "+" not in encoded


def test_ids_that_would_break_url_paths_stay_unencoded():
    assert encode_video_id("cgt-123", "model?with>odd~chars") == "cgt-123"


def test_decode_accepts_encoded_and_plain_ids():
    encoded = encode_video_id("cgt-123", "dreamina-seedance-2-5-260628")

    assert decode_video_id(encoded) == "cgt-123"
    assert decode_video_id(encoded.rstrip("=")) == "cgt-123"
    assert decode_video_id("cgt-123") == "cgt-123"
    assert decode_video_id("video-rh-abc") == "video-rh-abc"


def test_litellm_bracket_notation_rebuilds_nested_fields():
    # Multipart body as sent by LiteLLM >= 1.100 (see tasks/research/litellm-openai.md).
    items = [
        ("model", "dreamina-seedance-2-5-260628"),
        ("prompt", "fox"),
        ("seconds", "5"),
        ("reference_urls[][url]", "https://e/x.png"),
        ("reference_urls[][media_type]", "image"),
        ("reference_urls[][role]", "reference_image"),
        ("reference_urls[][real_human]", "false"),
        ("reference_urls[][url]", "https://e/z.png"),
        ("reference_urls[][media_type]", "image"),
        ("reference_urls[]", "https://e/y.png"),
        ("generate_audio", "false"),
        ("content[][type]", "text"),
        ("content[][text]", "hi"),
        ("provider_options[kling][mode]", "pro"),
        ("priority", "3"),
    ]

    data = form_to_data(items)

    assert data["reference_urls"] == [
        {
            "url": "https://e/x.png",
            "media_type": "image",
            "role": "reference_image",
            "real_human": False,
        },
        {"url": "https://e/z.png", "media_type": "image"},
        "https://e/y.png",
    ]
    assert data["content"] == [{"type": "text", "text": "hi"}]
    assert data["provider_options"] == {"kling": {"mode": "pro"}}
    assert data["generate_audio"] is False
    assert data["priority"] == 3


def test_structured_fields_accept_json_strings_in_forms():
    items = [
        ("model", "m"),
        ("references", json.dumps([{"type": "image", "url": "https://e/x.png"}])),
        ("shots", json.dumps([{"prompt": "a", "seconds": 2}])),
    ]

    data = form_to_data(items)

    assert data["references"] == [{"type": "image", "url": "https://e/x.png"}]
    assert data["shots"] == [{"prompt": "a", "seconds": 2}]


def test_extra_body_is_flattened_without_overriding_top_level_fields():
    items = [
        ("model", "m"),
        ("seed", "1"),
        ("extra_body", json.dumps({"seed": 9, "negative_prompt": "blur"})),
    ]

    data = form_to_data(items)

    assert data["seed"] == 1
    assert data["negative_prompt"] == "blur"
    assert "extra_body" not in data


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        proxy_api_key=None,
        require_proxy_api_key=False,
        public_base_url="https://seedance-proxy.example.com",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "proxy-jobs.db",
    )


def modelark(captured: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-123"})
        return httpx.Response(
            200,
            json={
                "id": "cgt-123",
                "model": "dreamina-seedance-2-5-260628",
                "status": "running",
            },
        )

    return httpx.MockTransport(handler)


async def call(settings: Settings, captured: list[httpx.Request], *requests):
    app = create_app(
        settings, ark_transport=modelark(captured), validate_startup_credentials=False
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        return [await send(client) for send in requests]


async def test_multipart_and_json_requests_reach_modelark_identically(
    settings: Settings,
):
    json_calls: list[httpx.Request] = []
    form_calls: list[httpx.Request] = []
    body = {
        "model": "dreamina-seedance-2-5-260628",
        "prompt": "fox",
        "seconds": 5,
        "generate_audio": False,
        "reference_urls": [
            {"url": "https://e/x.png", "media_type": "image"},
            {"url": "https://e/v.mp4", "media_type": "video"},
        ],
    }
    form = [
        ("model", "dreamina-seedance-2-5-260628"),
        ("prompt", "fox"),
        ("seconds", "5"),
        ("generate_audio", "false"),
        ("reference_urls[][url]", "https://e/x.png"),
        ("reference_urls[][media_type]", "image"),
        ("reference_urls[][url]", "https://e/v.mp4"),
        ("reference_urls[][media_type]", "video"),
    ]

    await call(settings, json_calls, lambda c: c.post("/v1/videos", json=body))
    await call(
        settings,
        form_calls,
        lambda c: c.post(
            "/v1/videos", files=[(key, (None, value)) for key, value in form]
        ),
    )

    assert json.loads(form_calls[0].content) == json.loads(json_calls[0].content)


async def test_create_returns_litellm_id_usable_for_follow_up_calls(
    settings: Settings,
):
    captured: list[httpx.Request] = []

    created, *_ = await call(
        settings,
        captured,
        lambda c: c.post(
            "/v1/videos",
            json={"model": "openai/dreamina-seedance-2-5-260628", "prompt": "fox"},
        ),
    )
    video_id = created.json()["id"]
    status, plain = await call(
        settings,
        captured,
        lambda c: c.get(f"/v1/videos/{video_id}"),
        lambda c: c.get("/v1/videos/cgt-123"),
    )

    assert litellm_decode(video_id) == {
        "provider": "openai",
        "model_id": "dreamina-seedance-2-5-260628",
        "video_id": "cgt-123",
    }
    assert status.status_code == 200
    assert status.json()["id"] == video_id
    assert plain.json()["id"] == video_id
    assert [r.url.path for r in captured[1:]] == [
        "/api/v3/contents/generations/tasks/cgt-123",
        "/api/v3/contents/generations/tasks/cgt-123",
    ]


async def test_json_with_form_strings_is_coerced_like_multipart(settings: Settings):
    # LiteLLM < 1.100 turns a form request without a file into JSON strings.
    typed: list[httpx.Request] = []
    stringly: list[httpx.Request] = []
    body = {"model": "dreamina-seedance-2-5-260628", "prompt": "fox"}

    await call(
        settings,
        typed,
        lambda c: c.post(
            "/v1/videos", json={**body, "generate_audio": False, "seed": 7}
        ),
    )
    await call(
        settings,
        stringly,
        lambda c: c.post(
            "/v1/videos", json={**body, "generate_audio": "false", "seed": "7"}
        ),
    )

    assert json.loads(stringly[0].content) == json.loads(typed[0].content)
