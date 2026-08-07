from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .assets import AssetClient
from .client import ModelArkClient
from .config import Settings
from .schemas import VideoObject
from .translation import byteplus_to_openai

TERMINAL_PROVIDER_STATUSES = {"succeeded", "failed", "cancelled", "expired"}


class AssetJobStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.lock, self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS asset_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    assets_json TEXT NOT NULL,
                    provider_id TEXT,
                    provider_json TEXT,
                    error_json TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    terminal_at INTEGER,
                    cleanup_done INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in (
            "request_json",
            "sources_json",
            "assets_json",
            "provider_json",
            "error_json",
        ):
            value = result.pop(key)
            result[key.removesuffix("_json")] = json.loads(value) if value else None
        result["cleanup_done"] = bool(result["cleanup_done"])
        return result

    def create(
        self, request: dict[str, Any], sources: list[dict[str, Any]]
    ) -> dict[str, Any]:
        now = int(time.time())
        job_id = f"video-rh-{uuid.uuid4().hex}"
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO asset_jobs
                    (id, status, request_json, sources_json, assets_json,
                     created_at, updated_at)
                VALUES (?, 'queued', ?, ?, '[]', ?, ?)
                """,
                (
                    job_id,
                    json.dumps(request, separators=(",", ":")),
                    json.dumps(sources, separators=(",", ":")),
                    now,
                    now,
                ),
            )
        return self.get(job_id) or {}

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM asset_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._decode(row) if row else None

    def active(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM asset_jobs WHERE terminal_at IS NULL ORDER BY created_at"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM asset_jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._decode(row) for row in rows]

    def update(self, job_id: str, **values: Any) -> None:
        allowed = {
            "status",
            "request",
            "sources",
            "assets",
            "provider_id",
            "provider",
            "error",
            "terminal_at",
            "cleanup_done",
        }
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in values.items():
            if key not in allowed:
                raise ValueError(f"Unsupported job field: {key}")
            column = (
                f"{key}_json"
                if key in {"request", "sources", "assets", "provider", "error"}
                else key
            )
            if key in {"request", "sources", "assets", "provider", "error"}:
                value = (
                    json.dumps(value, separators=(",", ":"))
                    if value is not None
                    else None
                )
            if key == "cleanup_done":
                value = int(bool(value))
            assignments.append(f"{column} = ?")
            params.append(value)
        assignments.append("updated_at = ?")
        params.extend((int(time.time()), job_id))
        with self.lock, self.connection:
            self.connection.execute(
                f"UPDATE asset_jobs SET {', '.join(assignments)} WHERE id = ?", params
            )

    def delete(self, job_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM asset_jobs WHERE id = ?", (job_id,))

    def close(self) -> None:
        with self.lock:
            self.connection.close()


class AssetJobManager:
    def __init__(
        self,
        settings: Settings,
        assets: AssetClient,
        ark: ModelArkClient,
        payload_builder: Callable[[dict[str, Any]], dict[str, Any]],
        remove_media: Callable[[str], bool],
    ) -> None:
        self.settings = settings
        self.assets = assets
        self.ark = ark
        self.payload_builder = payload_builder
        self.remove_media = remove_media
        self.store = AssetJobStore(settings.asset_job_db)
        self.semaphore = asyncio.Semaphore(settings.asset_worker_concurrency)
        self.running: set[str] = set()
        self.tasks: set[asyncio.Task[None]] = set()
        self.last_orphan_cleanup = 0.0

    def create(
        self, request: dict[str, Any], sources: list[dict[str, Any]]
    ) -> VideoObject:
        job = self.store.create(request, sources)
        self.schedule(job["id"])
        return self.to_video(job)

    def schedule(self, job_id: str) -> None:
        if job_id in self.running:
            return
        self.running.add(job_id)

        async def run() -> None:
            try:
                async with self.semaphore:
                    await self.process_once(job_id)
            finally:
                self.running.discard(job_id)

        task = asyncio.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def process_once(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job or job["terminal_at"] is not None:
            return
        try:
            age = int(time.time()) - job["created_at"]
            if (
                not job.get("provider_id")
                and age > self.settings.asset_max_processing_seconds
            ):
                raise TimeoutError(
                    "Real-human asset processing exceeded its configured lifetime"
                )
            if job.get("provider_id") and age > self.settings.asset_job_ttl_seconds:
                with suppress(Exception):
                    await self.ark.delete_task(str(job["provider_id"]))
                raise TimeoutError("Video task exceeded its configured lifetime")

            asset_records = list(job["assets"] or [])
            sources = list(job["sources"] or [])
            while len(asset_records) < len(sources):
                index = len(asset_records)
                source = sources[index]
                asset_id = await self.assets.create_asset(
                    source["url"],
                    source["kind"],
                    f"modelark-proxy-temp-{job_id[-20:]}-{index}",
                )
                asset_records.append({"id": asset_id, "source_index": index})
                self.store.update(job_id, assets=asset_records, status="preparing")

            active = True
            for record in asset_records:
                if record.get("status") == "Active":
                    continue
                if float(record.get("next_poll_at", 0)) > time.time():
                    active = False
                    continue
                result = await self.assets.get_asset(record["id"])
                status = str(result.get("Status", "Processing"))
                record["status"] = status
                if status == "Failed":
                    error = result.get("Error") or {}
                    raise RuntimeError(
                        error.get("Message", "BytePlus rejected the real-human asset")
                    )
                if status != "Active":
                    active = False
                    record["next_poll_at"] = (
                        time.time() + self.settings.asset_poll_interval_seconds
                    )
            self.store.update(job_id, assets=asset_records, status="preparing")
            if not active:
                return

            for source in sources:
                local_id = source.get("local_id")
                if isinstance(local_id, str):
                    self.remove_media(local_id)

            job = self.store.get(job_id) or job
            if not job.get("provider_id"):
                request = dict(job["request"])
                references = list(request.get("reference_assets") or [])
                for source, record in zip(sources, asset_records, strict=True):
                    references.append(
                        {
                            "id": record["id"],
                            "type": source["kind"],
                            "role": source.get("role"),
                        }
                    )
                request["reference_assets"] = references
                payload = self.payload_builder(request)
                result = await self.ark.create_task(payload)
                provider_id = str(result["id"])
                self.store.update(
                    job_id,
                    provider_id=provider_id,
                    provider=result,
                    request=request,
                    status="in_progress",
                )
                return

            provider = await self.ark.get_task(str(job["provider_id"]))
            provider_status = str(provider.get("status", "running"))
            if provider_status in TERMINAL_PROVIDER_STATUSES:
                status = "completed" if provider_status == "succeeded" else "failed"
                self.store.update(
                    job_id,
                    provider=provider,
                    status=status,
                    terminal_at=int(time.time()),
                )
                await self.cleanup(job_id)
            else:
                self.store.update(job_id, provider=provider, status="in_progress")
        except Exception as exc:  # noqa: BLE001 - persist any background failure
            self.store.update(
                job_id,
                status="failed",
                error={"code": "real_human_asset_error", "message": str(exc)},
                terminal_at=int(time.time()),
            )
            await self.cleanup(job_id)

    async def cleanup(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job or job["cleanup_done"]:
            return
        failed = False
        asset_records = list(job["assets"] or [])
        for record in asset_records:
            if record.get("deleted"):
                continue
            if float(record.get("cleanup_after", 0)) > time.time():
                failed = True
                continue
            try:
                await self.assets.delete_asset(record["id"])
                record["deleted"] = True
                record.pop("cleanup_after", None)
                self.store.update(job_id, assets=asset_records)
            except Exception:  # noqa: BLE001 - cleanup is retried persistently
                attempts = int(record.get("cleanup_attempts", 0)) + 1
                record["cleanup_attempts"] = attempts
                exponent = min(attempts, self.settings.asset_cleanup_retries)
                record["cleanup_after"] = int(time.time()) + min(2**exponent, 900)
                failed = True
        for source in job["sources"] or []:
            local_id = source.get("local_id")
            if isinstance(local_id, str):
                self.remove_media(local_id)
        self.store.update(job_id, assets=asset_records, cleanup_done=not failed)

    async def maintenance(self) -> None:
        now = int(time.time())
        for job in self.store.active():
            self.schedule(job["id"])
        for job in self.store.all():
            if job["terminal_at"] is not None and not job["cleanup_done"]:
                self.schedule_cleanup(job["id"])
            if (
                job["terminal_at"] is not None
                and now - job["terminal_at"] >= self.settings.asset_job_ttl_seconds
                and job["cleanup_done"]
            ):
                self.store.delete(job["id"])
        if (
            self.settings.real_human_assets_configured
            and time.monotonic() - self.last_orphan_cleanup
            >= self.settings.asset_orphan_cleanup_interval_seconds
        ):
            self.last_orphan_cleanup = time.monotonic()
            with suppress(Exception):
                await self.cleanup_orphans()

    async def cleanup_orphans(self) -> None:
        known = {
            record["id"]
            for job in self.store.all()
            for record in (job["assets"] or [])
            if not record.get("deleted")
        }
        cutoff = time.time() - self.settings.asset_orphan_ttl_seconds
        page = 1
        while True:
            result = await self.assets.list_assets(page)
            items = result.get("Items", [])
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                asset_id = item.get("Id")
                name = item.get("Name")
                created = item.get("CreateTime")
                if (
                    not isinstance(asset_id, str)
                    or asset_id in known
                    or not isinstance(name, str)
                    or not name.startswith("modelark-proxy-temp-")
                    or not isinstance(created, str)
                ):
                    continue
                try:
                    created_at = (
                        datetime.fromisoformat(created).astimezone(UTC).timestamp()
                    )
                except ValueError:
                    continue
                if created_at <= cutoff:
                    with suppress(Exception):
                        await self.assets.delete_asset(asset_id)
            total = result.get("TotalCount")
            if not items or not isinstance(total, int) or page * 100 >= total:
                return
            page += 1

    def schedule_cleanup(self, job_id: str) -> None:
        if job_id in self.running:
            return
        self.running.add(job_id)

        async def run() -> None:
            try:
                async with self.semaphore:
                    await self.cleanup(job_id)
            finally:
                self.running.discard(job_id)

        task = asyncio.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def cancel(self, job_id: str) -> VideoObject:
        job = self.store.get(job_id)
        if not job:
            raise KeyError(job_id)
        provider_id = job.get("provider_id")
        if provider_id:
            with suppress(Exception):
                await self.ark.delete_task(str(provider_id))
        self.store.update(
            job_id,
            status="failed",
            error={"code": "task_cancelled", "message": "Task was cancelled"},
            terminal_at=int(time.time()),
        )
        await self.cleanup(job_id)
        return self.to_video(self.store.get(job_id) or job)

    def to_video(self, job: dict[str, Any]) -> VideoObject:
        provider = job.get("provider")
        if isinstance(provider, dict) and provider.get("id") and job.get("provider_id"):
            video = byteplus_to_openai(provider)
            video.id = job["id"]
            if job.get("error"):
                video.error = job["error"]
            return video
        request = job.get("request") or {}
        requested_model = request.get("model")
        if not isinstance(requested_model, str) or not requested_model.strip():
            raise ValueError("Stored asset job has no model")
        return VideoObject(
            id=job["id"],
            status=job["status"]
            if job["status"] in {"completed", "failed"}
            else "queued",
            created_at=job["created_at"],
            progress=100 if job["status"] == "failed" else 10,
            seconds=str(request.get("duration"))
            if request.get("duration") is not None
            else None,
            size=request.get("size"),
            model=self.settings.resolve_model(requested_model.strip()),
            error=job.get("error"),
            provider_status="asset_processing"
            if job["status"] != "failed"
            else "failed",
        )

    def get_video(self, job_id: str) -> VideoObject | None:
        job = self.store.get(job_id)
        return self.to_video(job) if job else None

    def provider_id(self, job_id: str) -> str | None:
        job = self.store.get(job_id)
        return str(job["provider_id"]) if job and job.get("provider_id") else None

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.store.close()
