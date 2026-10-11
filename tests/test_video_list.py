"""GET /v1/videos across ModelArk tasks and the local job register (SPEC 11.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings
from modelark_proxy.ids import decode_video_id


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        ark_api_key="ark-test",
        kling_api_key="kling-key",
        proxy_api_key=None,
        require_proxy_api_key=False,
        media_dir=tmp_path / "media",
        asset_job_db=tmp_path / "asset-jobs.db",
        provider_job_db=tmp_path / "provider-jobs.db",
        output_dir=tmp_path / "outputs",
        provider_status_min_interval_seconds=0,
    )


def modelark(fail: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(500, json={"error": {"message": "down"}})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "cgt-old",
                        "model": "dreamina-seedance-2-5-260628",
                        "status": "succeeded",
                        "created_at": 100,
                        "updated_at": 120,
                    }
                ],
                "total": 1,
            },
        )

    return handler


def kling(request: httpx.Request) -> httpx.Response:
    data = {"task_id": "k1", "task_status": "submitted"}
    return httpx.Response(200, json={"code": 0, "message": "SUCCEED", "data": data})


async def run(tmp_path: Path, ark_handler, *paths) -> list[httpx.Response]:
    app = create_app(
        settings_for(tmp_path),
        ark_transport=httpx.MockTransport(ark_handler),
        kling_transport=httpx.MockTransport(kling),
        validate_startup_credentials=False,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client,
    ):
        created = await client.post(
            "/v1/videos", json={"model": "kling-3.0", "prompt": "fox", "seconds": 5}
        )
        assert created.status_code == 200, created.text
        responses: list[httpx.Response] = []
        for path in paths:
            target = path(responses) if callable(path) else path
            responses.append(await client.get(target))
        return responses


def ids(body: dict[str, Any]) -> list[str]:
    return [decode_video_id(item["id"]) for item in body["data"]]


async def test_list_combines_providers_newest_first(tmp_path: Path):
    (listed,) = await run(tmp_path, modelark(), "/v1/videos")

    body = listed.json()
    assert listed.status_code == 200
    assert ids(body)[1] == "cgt-old"
    assert ids(body)[0].startswith("vid-kling-")
    assert body["first_id"] == body["data"][0]["id"]
    assert body["last_id"] == body["data"][-1]["id"]
    assert body["has_more"] is False
    assert all(item["id"].startswith("video_") for item in body["data"])


async def test_list_pages_with_limit_and_after(tmp_path: Path):
    first, second = await run(
        tmp_path,
        modelark(),
        "/v1/videos?limit=1",
        lambda r: f"/v1/videos?limit=1&after={r[0].json()['last_id']}",
    )

    assert first.json()["has_more"] is True
    assert len(first.json()["data"]) == 1
    assert ids(second.json()) == ["cgt-old"]
    assert second.json()["has_more"] is False


async def test_list_filters_by_provider_status_and_order(tmp_path: Path):
    by_provider, by_status, ascending = await run(
        tmp_path,
        modelark(),
        "/v1/videos?provider=modelark",
        "/v1/videos?status=completed",
        "/v1/videos?order=asc",
    )

    assert ids(by_provider.json()) == ["cgt-old"]
    assert ids(by_status.json()) == ["cgt-old"]
    assert ids(ascending.json())[0] == "cgt-old"


async def test_a_failing_provider_becomes_a_warning(tmp_path: Path):
    (listed,) = await run(tmp_path, modelark(fail=True), "/v1/videos")

    body = listed.json()
    assert listed.status_code == 200
    assert len(body["data"]) == 1
    assert body["warnings"][0]["provider"] == "modelark"
