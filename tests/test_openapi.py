"""The published OpenAPI document describes the current video-only API."""

from __future__ import annotations

import warnings
from pathlib import Path

from modelark_proxy import __version__
from modelark_proxy.app import create_app
from modelark_proxy.config import Settings


def schema(tmp_path: Path) -> dict:
    app = create_app(
        Settings(
            proxy_api_key=None,
            require_proxy_api_key=False,
            media_dir=tmp_path / "media",
            asset_job_db=tmp_path / "asset-jobs.db",
            provider_job_db=tmp_path / "provider-jobs.db",
            output_dir=tmp_path / "outputs",
        ),
        validate_startup_credentials=False,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return app.openapi()


def test_openapi_names_the_studio_and_its_version(tmp_path: Path):
    info = schema(tmp_path)["info"]

    assert info["title"] == "AI Video Studio API"
    assert info["version"] == __version__
    for provider in ("Seedance", "Veo", "Omni", "Kling"):
        assert provider in info["description"]


def test_every_operation_is_tagged_and_unique(tmp_path: Path):
    spec = schema(tmp_path)
    operations = [op for ops in spec["paths"].values() for op in ops.values()]

    assert all(op.get("tags") for op in operations)
    ids = [op["operationId"] for op in operations]
    assert len(ids) == len(set(ids))
    assert "/v1/audio/speech" not in spec["paths"]
