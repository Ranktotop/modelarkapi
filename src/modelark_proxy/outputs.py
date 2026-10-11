"""Proxy-held copies of generation results.

Some upstreams return video bytes inline (Vertex, Omni) and others hand out
hotlink-protected URLs (Kling). Those results are kept here until the job
expires, so content requests never depend on the upstream link.
"""

from __future__ import annotations

import mimetypes
import re
import shutil
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class OutputStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, job_id: str) -> Path:
        if not _SAFE_NAME.fullmatch(job_id):
            raise ValueError(f"Invalid job ID: {job_id!r}")
        return self.root / job_id

    async def save(
        self,
        job_id: str,
        index: int,
        variant: str,
        chunks: AsyncIterable[bytes],
        mime_type: str,
    ) -> dict[str, Any]:
        if not _SAFE_NAME.fullmatch(variant):
            raise ValueError(f"Invalid output variant: {variant!r}")
        directory = self._job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        extension = mimetypes.guess_extension(mime_type) or ".bin"
        target = directory / f"{int(index)}-{variant}{extension}"
        partial = target.with_suffix(target.suffix + ".part")
        size = 0
        with partial.open("wb") as handle:
            async for chunk in chunks:
                handle.write(chunk)
                size += len(chunk)
        partial.replace(target)
        return {"path": target, "bytes": size, "mime_type": mime_type}

    def path(self, job_id: str, index: int, variant: str) -> Path | None:
        directory = self._job_dir(job_id)
        if not directory.is_dir():
            return None
        matches = [
            candidate
            for candidate in directory.glob(f"{int(index)}-{variant}.*")
            if not candidate.name.endswith(".part")
        ]
        return matches[0] if matches else None

    def delete(self, job_id: str) -> None:
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
