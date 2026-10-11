"""Kling 3.0 Omni and O1 through the omni-video endpoint (T15)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from kling_helpers import strip_external

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_URI = "data:image/png;base64," + base64.b64encode(PNG).decode()
PNG_B64 = base64.b64encode(PNG).decode()
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 24
MP4_URI = "data:video/mp4;base64," + base64.b64encode(MP4).decode()
VIDEO_URL = "https://videos.example.com/clip.mp4"


class FakeKling:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            200, json={"code": 0, "data": {"task_id": "T1", "task_status": "submitted"}}
        )

    def created(self) -> dict[str, Any]:
        request = next(r for r in self.requests if r.method == "POST")
        assert request.url.path == "/v1/videos/omni-video"
        return strip_external(json.loads(request.content))


def settings_for(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        proxy_api_key=None,
        require_proxy_api_key=False,
        kling_api_key="kling-key",
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        **extra,
    )


async def post(
    tmp_path: Path, body: dict[str, Any], **settings: Any
) -> tuple[httpx.Response, FakeKling]:
    fake = FakeKling()
    app = create_app(
        settings_for(tmp_path, **settings),
        kling_transport=httpx.MockTransport(fake),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        response = await client.post("/v1/videos", json=body)
        if body.get("model") == "__models__":
            response = await client.get("/v1/models")
    return response, fake


async def test_omni_models_are_listed(tmp_path: Path):
    response, _ = await post(tmp_path, {"model": "__models__"})

    caps = {m["id"]: m["capabilities"] for m in response.json()["data"]}
    assert set(caps["kling-3.0-omni"]["tasks"]) == {
        "text_to_video",
        "image_to_video",
        "first_last_frame",
        "reference_to_video",
        "edit",
        "multi_shot",
    }
    assert "4k" in caps["kling-3.0-omni"]["parameters"]["resolution"]["values"]
    assert caps["kling-o1"]["parameters"]["seconds"]["values"] == list(range(3, 11))
    assert "multi_shot" not in caps["kling-o1"]["tasks"]


async def test_text_to_video_goes_through_omni_video(tmp_path: Path):
    response, fake = await post(
        tmp_path, {"model": "kling-3.0-omni", "prompt": "a fox"}
    )

    assert response.status_code == 200
    assert fake.created() == {
        "model_name": "kling-v3-omni",
        "prompt": "a fox",
        "duration": "5",
        "mode": "std",
        "aspect_ratio": "16:9",
    }


async def test_references_become_image_element_and_feature_video_lists(tmp_path: Path):
    response, fake = await post(
        tmp_path,
        {
            "model": "kling-3.0-omni",
            "prompt": "<<<image_1>>> dances like <<<video_1>>>",
            "task": "reference_to_video",
            "references": [
                {"type": "image", "url": PNG_URI},
                {"asset_id": "asset-kling-element-123"},
                {"type": "video", "url": VIDEO_URL},
            ],
        },
    )

    assert response.status_code == 200
    body = fake.created()
    assert body["image_list"] == [{"image_url": PNG_B64}]
    assert body["element_list"] == [{"element_id": 123}]
    assert body["video_list"] == [
        {"video_url": VIDEO_URL, "refer_type": "feature", "keep_original_sound": "no"}
    ]
    assert body["aspect_ratio"] == "16:9"


async def test_edit_uses_the_base_video_and_keeps_its_length(tmp_path: Path):
    response, fake = await post(
        tmp_path,
        {
            "model": "kling-o1",
            "task": "edit",
            "prompt": "make it night",
            "references": [{"type": "video", "url": VIDEO_URL}],
            "provider_options": {"kling": {"keep_original_sound": "yes"}},
        },
    )

    assert response.status_code == 200
    body = fake.created()
    assert body["video_list"] == [
        {"video_url": VIDEO_URL, "refer_type": "base", "keep_original_sound": "yes"}
    ]
    assert "duration" not in body
    assert "aspect_ratio" not in body


async def test_first_and_last_frames_are_typed(tmp_path: Path):
    response, fake = await post(
        tmp_path,
        {
            "model": "kling-o1",
            "prompt": "morph",
            "seconds": 7,
            "references": [
                {"type": "image", "url": PNG_URI, "role": "first_frame"},
                {
                    "type": "image",
                    "url": "https://images.example.com/end.png",
                    "role": "last_frame",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert fake.created()["image_list"] == [
        {"image_url": PNG_B64, "type": "first_frame"},
        {"image_url": "https://images.example.com/end.png", "type": "end_frame"},
    ]


async def test_uploaded_videos_are_served_from_the_proxy(tmp_path: Path):
    response, fake = await post(
        tmp_path,
        {
            "model": "kling-o1",
            "task": "edit",
            "prompt": "x",
            "references": [{"type": "video", "url": MP4_URI}],
        },
        public_base_url="https://proxy.example.com",
    )

    assert response.status_code == 200
    assert fake.created()["video_list"][0]["video_url"].startswith(
        "https://proxy.example.com/media/reference/"
    )


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {
                "model": "kling-o1",
                "seconds": 7,
                "references": [{"type": "image", "url": PNG_URI}],
            },
            "unsupported_parameter",
        ),
        (
            {
                "model": "kling-3.0-omni",
                "task": "reference_to_video",
                "references": [{"type": "video", "url": VIDEO_URL}] * 2,
            },
            "reference_limit",
        ),
        (
            {
                "model": "kling-3.0-omni",
                "task": "reference_to_video",
                "generate_audio": True,
                "references": [{"type": "video", "url": VIDEO_URL}],
            },
            "unsupported_parameter",
        ),
        (
            {
                "model": "kling-3.0-omni",
                "task": "reference_to_video",
                "references": [{"type": "image", "url": PNG_URI}] * 5
                + [{"type": "video", "url": VIDEO_URL}],
            },
            "reference_limit",
        ),
        (
            {
                "model": "kling-o1",
                "references": [
                    {"type": "image", "url": PNG_URI, "role": "first_frame"},
                    {"type": "image", "url": PNG_URI, "role": "last_frame"},
                    {"asset_id": "asset-kling-element-1"},
                ],
            },
            "reference_limit",
        ),
        (
            {
                "model": "kling-o1",
                "task": "edit",
                "references": [{"type": "video", "url": MP4_URI}],
            },
            "public_base_url_required",
        ),
    ],
)
async def test_omni_rules_fail_fast(tmp_path: Path, body: dict[str, Any], code: str):
    response, fake = await post(tmp_path, {"prompt": "x", **body})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert not any(r.method == "POST" for r in fake.requests)


# --- T16: motion control -------------------------------------------------------


async def post_motion(
    tmp_path: Path, body: dict[str, Any]
) -> tuple[httpx.Response, dict[str, Any] | None]:
    response, fake = await post(tmp_path, body)
    posted = [r for r in fake.requests if r.method == "POST"]
    if not posted:
        return response, None
    assert posted[0].url.path == "/v1/videos/motion-control"
    return response, strip_external(json.loads(posted[0].content))


async def test_motion_control_moves_the_character_like_the_video(tmp_path: Path):
    response, body = await post_motion(
        tmp_path,
        {
            "model": "kling-3.0",
            "prompt": "dance",
            "resolution": "1080p",
            "references": [
                {"type": "image", "url": PNG_URI, "role": "subject"},
                {"type": "video", "url": VIDEO_URL, "role": "motion"},
            ],
            "provider_options": {
                "kling": {"character_orientation": "video", "keep_original_sound": "no"}
            },
        },
    )

    assert response.status_code == 200
    assert body == {
        "model_name": "kling-v3",
        "prompt": "dance",
        "image_url": PNG_B64,
        "video_url": VIDEO_URL,
        "character_orientation": "video",
        "keep_original_sound": "no",
        "mode": "pro",
    }


async def test_motion_control_defaults_and_elements(tmp_path: Path):
    response, body = await post_motion(
        tmp_path,
        {
            "model": "kling-3.0",
            "references": [
                {"asset_id": "asset-kling-element-123"},
                {"type": "video", "url": VIDEO_URL, "role": "motion"},
            ],
        },
    )

    assert response.status_code == 200
    assert body["element_list"] == [{"element_id": 123}]
    assert body["character_orientation"] == "image"
    assert body["mode"] == "std"
    assert "image_url" not in body


@pytest.mark.parametrize(
    "body",
    [
        {
            "model": "kling-2.5-turbo",
            "references": [
                {"type": "image", "url": PNG_URI},
                {"type": "video", "url": VIDEO_URL, "role": "motion"},
            ],
        },
        {
            "model": "kling-3.0",
            "references": [{"type": "video", "url": VIDEO_URL, "role": "motion"}],
        },
        {
            "model": "kling-3.0",
            "resolution": "4k",
            "references": [
                {"type": "image", "url": PNG_URI},
                {"type": "video", "url": VIDEO_URL, "role": "motion"},
            ],
        },
        {
            "model": "kling-2.6",
            "seconds": 5,
            "references": [
                {"type": "image", "url": PNG_URI},
                {"type": "video", "url": VIDEO_URL, "role": "motion"},
            ],
        },
    ],
)
async def test_motion_control_rules(tmp_path: Path, body: dict[str, Any]):
    response, posted = await post_motion(tmp_path, body)

    assert response.status_code in {400, 404}
    assert posted is None
