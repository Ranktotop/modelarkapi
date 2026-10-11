"""Kling elements and voices as unified assets (docs/SPEC.md, sections 3.3 and 16.4).

Creating an element or voice is an asynchronous Kling task. Until it is done
the asset has a task-based ID (`asset-kling-element-task-<task>`); afterwards
it is known by Kling's own ID (`asset-kling-element-<element_id>`).
"""

from __future__ import annotations

from typing import Any

from ...errors import ApiError
from ...references import ReferenceResolver
from ...validation import ContractError
from .client import KlingClient

PREFIXES = {"element": "asset-kling-element-", "voice": "asset-kling-voice-"}
TASK_MARKER = "task-"
ENDPOINTS = {
    "element": {
        "custom": "/v1/general/advanced-custom-elements",
        "preset": "/v1/general/advanced-presets-elements",
        "delete": "/v1/general/delete-advanced-elements",
        "result": "elements",
        "id": "element_id",
        "name": "element_name",
    },
    "voice": {
        "custom": "/v1/general/custom-voices",
        "preset": "/v1/general/presets-voices",
        "delete": "/v1/general/delete-voices",
        "result": "voices",
        "id": "voice_id",
        "name": "voice_name",
    },
}
RUNNING = {"submitted", "processing"}


def parse_asset_id(asset_id: str) -> tuple[str, str, bool]:
    """(type, Kling ID or task ID, is_task) for an `asset-kling-…` ID."""
    for kind, prefix in PREFIXES.items():
        if asset_id.startswith(prefix):
            value = asset_id[len(prefix) :]
            if value.startswith(TASK_MARKER):
                return kind, value[len(TASK_MARKER) :], True
            return kind, value, False
    raise ApiError(f"Unknown asset '{asset_id}'", 404, "not_found")


def native_id(value: str) -> int | str:
    """Kling element IDs are numbers (voice IDs stay strings; see the caller)."""
    return int(value) if value.isdigit() else value


def to_asset(kind: str, task: dict[str, Any]) -> dict[str, Any]:
    spec = ENDPOINTS[kind]
    status = str(task.get("task_status") or "")
    items = (task.get("task_result") or {}).get(spec["result"]) or []
    item = items[0] if items else {}
    if status in {"succeed", "succeeded"} and item.get(spec["id"]) is not None:
        asset_id = f"{PREFIXES[kind]}{item[spec['id']]}"
        state = "ready"
    else:
        asset_id = f"{PREFIXES[kind]}{TASK_MARKER}{task.get('task_id')}"
        state = "processing" if status in RUNNING else "failed"
    return {
        "id": asset_id,
        "object": "asset",
        "provider": "kling",
        "type": kind,
        "name": item.get(spec["name"]),
        "status": state,
        "error": task.get("task_status_msg") if state == "failed" else None,
        "details": item or task,
    }


class KlingAssets:
    def __init__(self, client: KlingClient, references: ReferenceResolver) -> None:
        self.client = client
        self.references = references

    async def _image(self, reference: dict[str, Any]) -> str:
        url = reference.get("url")
        if isinstance(url, str) and url.startswith("https://"):
            return url
        return (await self.references.fetch(reference)).base64

    async def create(self, body: dict[str, Any]) -> dict[str, Any]:
        kind = body.get("type")
        name = body.get("name")
        if kind not in ENDPOINTS:
            raise ContractError("type must be element or voice", param="type")
        if not isinstance(name, str) or not 1 <= len(name) <= 20:
            raise ContractError("name must have 1 to 20 characters", param="name")
        references = body.get("references") or []
        if not isinstance(references, list) or not references:
            raise ContractError(
                "At least one reference is required", param="references"
            )
        if kind == "element":
            payload = await self._element(body, references)
        else:
            payload = await self._voice(name, references)
        created = await self.client.call(
            "POST", ENDPOINTS[kind]["custom"], json=payload
        )
        return to_asset(kind, created)

    async def _element(
        self, body: dict[str, Any], references: list[dict[str, Any]]
    ) -> dict[str, Any]:
        description = body.get("description")
        if not isinstance(description, str) or not 1 <= len(description) <= 100:
            raise ContractError(
                "description must have 1 to 100 characters", param="description"
            )
        images = [r for r in references if r.get("type") == "image"]
        videos = [r for r in references if r.get("type") == "video"]
        payload: dict[str, Any] = {
            "element_name": body["name"],
            "element_description": description,
        }
        if videos:
            if images or len(videos) != 1:
                raise ContractError(
                    "A video element takes exactly one video and no images",
                    param="references",
                )
            payload["reference_type"] = "video_refer"
            payload["element_video_list"] = {
                "refer_videos": [
                    {"video_url": await self.references.public_url(videos[0])}
                ]
            }
        else:
            frontal = next(
                (r for r in images if r.get("role") == "frontal"),
                images[0] if images else None,
            )
            others = [r for r in images if r is not frontal]
            if frontal is None or not 1 <= len(others) <= 3:
                raise ContractError(
                    "An image element takes one frontal image and 1 to 3 more images",
                    param="references",
                )
            payload["reference_type"] = "image_refer"
            payload["element_image_list"] = {
                "frontal_image": await self._image(frontal),
                "refer_images": [{"image_url": await self._image(r)} for r in others],
            }
        voice = body.get("voice")
        if voice:
            kind, value, is_task = parse_asset_id(str(voice))
            if kind != "voice" or is_task:
                raise ContractError("voice must be a ready voice asset", param="voice")
            payload["element_voice_id"] = value
        tags = body.get("tags") or []
        if tags:
            payload["tag_list"] = [{"tag_id": tag} for tag in tags]
        return payload

    async def _voice(
        self, name: str, references: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if len(references) != 1 or references[0].get("type") not in {"audio", "video"}:
            raise ContractError(
                "A voice takes exactly one audio or video reference", param="references"
            )
        return {
            "voice_name": name,
            "voice_url": await self.references.public_url(references[0]),
        }

    async def get(self, asset_id: str) -> dict[str, Any]:
        kind, value, is_task = parse_asset_id(asset_id)
        if is_task:
            task = await self.client.call("GET", f"{ENDPOINTS[kind]['custom']}/{value}")
            return to_asset(kind, task)
        for asset in await self.list(kind, "custom") + await self.list(kind, "preset"):
            if asset["id"] == asset_id:
                return asset
        raise ApiError(f"Asset '{asset_id}' not found", 404, "not_found")

    async def list(self, kind: str, scope: str = "custom") -> list[dict[str, Any]]:
        if kind not in ENDPOINTS or scope not in {"custom", "preset"}:
            raise ContractError("type must be element or voice, scope custom or preset")
        tasks = await self.client.call(
            "GET", ENDPOINTS[kind][scope], params={"pageNum": 1, "pageSize": 500}
        )
        assets = []
        for task in tasks or []:
            items = (task.get("task_result") or {}).get(ENDPOINTS[kind]["result"]) or []
            if len(items) > 1:
                assets.extend(
                    to_asset(
                        kind,
                        {**task, "task_result": {ENDPOINTS[kind]["result"]: [item]}},
                    )
                    for item in items
                )
            else:
                assets.append(to_asset(kind, task))
        return assets

    async def delete(self, asset_id: str) -> dict[str, Any]:
        kind, value, is_task = parse_asset_id(asset_id)
        if is_task:
            raise ContractError("Only ready assets can be deleted", param="asset_id")
        await self.client.call(
            "POST", ENDPOINTS[kind]["delete"], json={ENDPOINTS[kind]["id"]: value}
        )
        return {"id": asset_id, "object": "asset.deleted", "deleted": True}
