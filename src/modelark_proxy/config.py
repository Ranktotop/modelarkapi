from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", validate_default=True
    )

    ark_api_key: str = ""
    ark_base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3"
    credential_validation_interval_seconds: float = Field(default=10_800, gt=0)
    credential_validation_timeout_seconds: float = Field(default=10.0, gt=0)
    proxy_api_key: str | None = None
    require_proxy_api_key: bool = False
    public_base_url: str | None = None
    model_cache_ttl_seconds: int = 300
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
    byteplus_access_key_id: str = ""
    byteplus_secret_access_key: str = ""
    byteplus_asset_group_id: str = ""
    byteplus_project_name: str = "default"
    byteplus_asset_region: str = "ap-southeast-1"
    byteplus_asset_endpoint: str = "https://ark.ap-southeast-1.byteplusapi.com"
    asset_job_db: Path = Path("./data/proxy-jobs.db")
    asset_poll_interval_seconds: float = 5.0
    asset_maintenance_interval_seconds: float = 2.0
    asset_max_processing_seconds: int = 3600
    asset_job_ttl_seconds: int = 86_400
    asset_worker_concurrency: int = 10
    asset_cleanup_retries: int = 5
    asset_orphan_cleanup_interval_seconds: int = 900
    asset_orphan_ttl_seconds: int = 86_400

    @field_validator("allowed_download_host_suffixes", mode="before")
    @classmethod
    def parse_host_suffixes(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    def resolve_model(self, requested: str) -> str:
        return requested.removeprefix("openai/")

    @model_validator(mode="after")
    def validate_required_credentials(self) -> Settings:
        if self.require_proxy_api_key and not self.proxy_api_key:
            raise ValueError(
                "PROXY_API_KEY is required when REQUIRE_PROXY_API_KEY=true"
            )
        if self.require_proxy_api_key and len(self.proxy_api_key or "") < 32:
            raise ValueError(
                "PROXY_API_KEY must contain at least 32 characters in protected mode"
            )
        return self

    @property
    def real_human_assets_configured(self) -> bool:
        return all(
            (
                self.byteplus_access_key_id,
                self.byteplus_secret_access_key,
                self.byteplus_asset_group_id,
            )
        )

    @property
    def model_management_configured(self) -> bool:
        return bool(self.byteplus_access_key_id and self.byteplus_secret_access_key)
