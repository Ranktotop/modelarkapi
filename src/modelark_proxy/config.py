from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ark_api_key: str = ""
    ark_base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3"
    proxy_api_key: str | None = None
    public_base_url: str | None = None
    default_model: str = "dreamina-seedance-2-0-260128"
    model_map: dict[str, str] = Field(default_factory=dict)
    default_generate_audio: bool = True
    media_dir: Path = Path("./data/references")
    media_ttl_seconds: int = 86_400
    media_cleanup_interval_seconds: int = 900
    max_upload_bytes: int = 200 * 1024 * 1024
    request_timeout_seconds: float = 60.0
    download_timeout_seconds: float = 600.0
    max_upstream_connections: int = 100
    max_keepalive_connections: int = 20
    allowed_download_host_suffixes: list[str] = Field(
        default_factory=lambda: [".bytepluses.com", ".volces.com"]
    )

    @field_validator("model_map", mode="before")
    @classmethod
    def parse_model_map(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value

    @field_validator("allowed_download_host_suffixes", mode="before")
    @classmethod
    def parse_host_suffixes(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    def resolve_model(self, requested: str | None) -> str:
        if not requested:
            return self.default_model
        bare = requested.removeprefix("openai/")
        return self.model_map.get(requested, self.model_map.get(bare, bare))
