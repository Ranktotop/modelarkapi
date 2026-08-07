from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import httpx

from .config import Settings


class AssetAPIError(RuntimeError):
    def __init__(self, message: str, body: Any = None):
        super().__init__(message)
        self.body = body


class AssetClient:
    """Small async client for the AK/SK-authenticated ModelArk Assets API."""

    version = "2024-01-01"
    service = "ark"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url=settings.byteplus_asset_endpoint.rstrip("/"),
            timeout=settings.request_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.max_upstream_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

    def _signed_headers(
        self, method: str, path: str, query: dict[str, str], body: bytes
    ) -> dict[str, str]:
        now = datetime.now(UTC)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date = timestamp[:8]
        parsed = urlparse(self.settings.byteplus_asset_endpoint)
        host = parsed.netloc
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_query = urlencode(sorted(query.items()), quote_via=quote, safe="-_.~")
        canonical_headers = (
            f"content-type:application/json\nhost:{host}\n"
            f"x-content-sha256:{payload_hash}\nx-date:{timestamp}\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = (
            f"{method}\n{path}\n{canonical_query}\n{canonical_headers}\n"
            f"{signed_headers}\n{payload_hash}"
        )
        scope = f"{date}/{self.settings.byteplus_asset_region}/{self.service}/request"
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                timestamp,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )

        def sign(key: bytes, value: str) -> bytes:
            return hmac.new(key, value.encode(), hashlib.sha256).digest()

        signing_key = sign(
            sign(
                sign(
                    sign(self.settings.byteplus_secret_access_key.encode(), date),
                    self.settings.byteplus_asset_region,
                ),
                self.service,
            ),
            "request",
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        authorization = (
            "HMAC-SHA256 "
            f"Credential={self.settings.byteplus_access_key_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Content-Type": "application/json",
            "Host": host,
            "X-Content-Sha256": payload_hash,
            "X-Date": timestamp,
            "Authorization": authorization,
        }

    async def call(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        query = {"Action": action, "Version": self.version}
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        response = await self.http.post(
            "/",
            params=query,
            content=body,
            headers=self._signed_headers("POST", "/", query, body),
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise AssetAPIError(
                f"Assets API returned HTTP {response.status_code} without JSON"
            ) from exc
        if response.is_error or not isinstance(data, dict):
            error = data.get("ResponseMetadata", {}).get("Error", data)
            message = (
                error.get("Message", str(error))
                if isinstance(error, dict)
                else str(error)
            )
            raise AssetAPIError(message, data)
        metadata_error = data.get("ResponseMetadata", {}).get("Error")
        if metadata_error:
            raise AssetAPIError(
                metadata_error.get("Message", str(metadata_error)), data
            )
        result = data.get("Result", data)
        if not isinstance(result, dict):
            raise AssetAPIError(f"Assets API {action} returned no result object", data)
        return result

    async def create_asset(self, url: str, kind: str, name: str) -> str:
        result = await self.call(
            "CreateAsset",
            {
                "GroupId": self.settings.byteplus_asset_group_id,
                "URL": url,
                "AssetType": kind.capitalize(),
                "Name": name[:64],
                "ProjectName": self.settings.byteplus_project_name,
            },
        )
        asset_id = result.get("Id")
        if not isinstance(asset_id, str):
            raise AssetAPIError("CreateAsset returned no asset ID", result)
        return asset_id

    async def get_asset(self, asset_id: str) -> dict[str, Any]:
        return await self.call(
            "GetAsset",
            {"Id": asset_id, "ProjectName": self.settings.byteplus_project_name},
        )

    async def delete_asset(self, asset_id: str) -> None:
        await self.call(
            "DeleteAsset",
            {"Id": asset_id, "ProjectName": self.settings.byteplus_project_name},
        )

    async def list_asset_groups(self) -> dict[str, Any]:
        return await self.call(
            "ListAssetGroups",
            {
                "Filter": {
                    "GroupIds": [self.settings.byteplus_asset_group_id],
                    "GroupType": "LivenessFace",
                },
                "PageNumber": 1,
                "PageSize": 10,
                "ProjectName": self.settings.byteplus_project_name,
            },
        )

    async def list_assets(self, page_number: int = 1) -> dict[str, Any]:
        return await self.call(
            "ListAssets",
            {
                "Filter": {
                    "GroupIds": [self.settings.byteplus_asset_group_id],
                    "GroupType": "LivenessFace",
                    "Name": "modelark-proxy-temp-",
                },
                "PageNumber": page_number,
                "PageSize": 100,
                "SortBy": "CreateTime",
                "SortOrder": "Asc",
                "ProjectName": self.settings.byteplus_project_name,
            },
        )
