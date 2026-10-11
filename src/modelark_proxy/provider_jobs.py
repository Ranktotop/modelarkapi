"""Local job register for providers whose jobs are not ModelArk tasks.

Google operations and interactions, Kling tasks, and multi-step flows such as
lip sync get a stable proxy ID (`vid-<slug>-<uuid>`). The register maps it to
the upstream reference, keeps outputs and errors, and survives restarts.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from .schemas import VideoObject

if TYPE_CHECKING:
    from .outputs import OutputStore

TERMINAL_STATUSES = {"completed", "failed"}
_JSON_FIELDS = (
    "request",
    "upstream",
    "state",
    "outputs",
    "error",
    "usage",
    "adjustments",
    "metadata",
)
_PLAIN_FIELDS = (
    "status",
    "provider_status",
    "progress",
    "completed_at",
    "expires_at",
    "worker",
)


class ProviderJobStore:
    def __init__(self, path: Path, ttl_seconds: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = RLock()
        json_columns = ",\n".join(f"{field}_json TEXT" for field in _JSON_FIELDS)
        with self.lock, self.connection:
            self.connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS provider_jobs (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_status TEXT,
                    progress INTEGER,
                    worker INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    expires_at INTEGER NOT NULL,
                    {json_columns}
                )
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        job = dict(row)
        for field in _JSON_FIELDS:
            value = job.pop(f"{field}_json")
            job[field] = json.loads(value) if value else None
        job["worker"] = bool(job["worker"])
        return job

    def create(
        self,
        provider: str,
        model: str,
        task: str,
        request: dict[str, Any],
        *,
        slug: str | None = None,
        upstream: dict[str, Any] | None = None,
        worker: bool = False,
    ) -> dict[str, Any]:
        now = int(time.time())
        job_id = f"vid-{slug or provider}-{uuid.uuid4().hex}"
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO provider_jobs
                    (id, provider, model, task, status, worker, created_at,
                     updated_at, expires_at, request_json, upstream_json)
                VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    provider,
                    model,
                    task,
                    int(worker),
                    now,
                    now,
                    now + self.ttl_seconds,
                    json.dumps(request, separators=(",", ":")),
                    json.dumps(upstream, separators=(",", ":")) if upstream else None,
                ),
            )
        return self.get(job_id) or {}

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM provider_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._decode(row) if row else None

    def update(self, job_id: str, **values: Any) -> None:
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in values.items():
            if key in _JSON_FIELDS:
                assignments.append(f"{key}_json = ?")
                params.append(
                    json.dumps(value, separators=(",", ":"))
                    if value is not None
                    else None
                )
            elif key in _PLAIN_FIELDS:
                assignments.append(f"{key} = ?")
                params.append(int(value) if key == "worker" else value)
            else:
                raise ValueError(f"Unsupported job field: {key}")
        if values.get("status") in TERMINAL_STATUSES and "completed_at" not in values:
            assignments.append("completed_at = COALESCE(completed_at, ?)")
            params.append(int(time.time()))
        assignments.append("updated_at = ?")
        params.extend((int(time.time()), job_id))
        with self.lock, self.connection:
            self.connection.execute(
                f"UPDATE provider_jobs SET {', '.join(assignments)} WHERE id = ?",
                params,
            )

    def active(self, *, worker_only: bool = False) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM provider_jobs WHERE status NOT IN ('completed', 'failed')"
        )
        if worker_only:
            query += " AND worker = 1"
        with self.lock:
            rows = self.connection.execute(query + " ORDER BY created_at").fetchall()
        return [self._decode(row) for row in rows]

    def list(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("provider", provider),
            ("model", model),
            ("status", status),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.lock:
            rows = self.connection.execute(
                f"SELECT * FROM provider_jobs {where} ORDER BY created_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def delete(self, job_id: str) -> None:
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM provider_jobs WHERE id = ?", (job_id,))

    def expired(self, now: int | None = None) -> list[str]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT id FROM provider_jobs WHERE expires_at <= ?",
                (int(time.time()) if now is None else now,),
            ).fetchall()
        return [row["id"] for row in rows]

    def to_video(self, job: dict[str, Any]) -> VideoObject:
        status = job["status"]
        progress = job["progress"]
        if progress is None:
            progress = {"queued": 0, "in_progress": 50}.get(status, 100)
        request = job["request"] or {}
        seconds = request.get("seconds")
        return VideoObject(
            id=job["id"],
            status=status,
            created_at=job["created_at"],
            completed_at=job["completed_at"] if status == "completed" else None,
            expires_at=job["expires_at"],
            error=job["error"],
            progress=progress,
            seconds=str(seconds) if seconds is not None else None,
            size=request.get("size"),
            model=job["model"],
            usage=job["usage"],
            provider=job["provider"],
            task=job["task"],
            provider_status=job["provider_status"],
            outputs=job["outputs"] or [],
            adjustments=job["adjustments"] or [],
            metadata=job["metadata"] or {},
        )

    def close(self) -> None:
        with self.lock:
            self.connection.close()


def purge_expired(store: ProviderJobStore, outputs: OutputStore) -> list[str]:
    """Delete expired jobs together with their stored outputs."""
    expired = store.expired()
    for job_id in expired:
        outputs.delete(job_id)
        store.delete(job_id)
    return expired
