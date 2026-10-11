"""Bounded background execution for jobs that cannot be polled lazily.

Synchronous upstreams and multi-step flows (lip sync, multi-element editing)
need someone to drive them. A handler advances one job and records progress in
the register, so a restart resumes every unfinished worker job.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from .provider_jobs import TERMINAL_STATUSES, ProviderJobStore
from .retry import TransientUpstreamError, backoff_delay, is_retryable

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class JobRunner:
    def __init__(
        self,
        store: ProviderJobStore,
        concurrency: int,
        *,
        poll_interval_seconds: float = 5.0,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 60.0,
    ) -> None:
        self.store = store
        self.semaphore = asyncio.Semaphore(concurrency)
        self.poll_interval_seconds = poll_interval_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.handlers: dict[str, Handler] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def register(self, provider: str, handler: Handler) -> None:
        self.handlers[provider] = handler

    def schedule(self, job_id: str) -> None:
        if job_id in self.tasks:
            return
        task = asyncio.create_task(self._run(job_id))
        self.tasks[job_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(job_id, None))

    def resume(self) -> None:
        for job in self.store.active(worker_only=True):
            if job["provider"] in self.handlers:
                self.schedule(job["id"])

    async def _run(self, job_id: str) -> None:
        attempt = 0
        while True:
            job = self.store.get(job_id)
            if not job or job["status"] in TERMINAL_STATUSES:
                return
            handler = self.handlers.get(job["provider"])
            if handler is None:
                return
            try:
                async with self.semaphore:
                    await handler(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, TransientUpstreamError) or is_retryable(exc):
                    attempt += 1
                    delay = backoff_delay(
                        attempt, self.retry_base_seconds, self.retry_max_seconds
                    )
                    logger.warning(
                        "Job %s hit a transient upstream error (%s); retrying in %.1fs",
                        job_id,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Job %s failed in its worker", job_id)
                self.store.update(
                    job_id,
                    status="failed",
                    error={
                        "code": "upstream_error",
                        "message": str(exc) or type(exc).__name__,
                    },
                )
                return
            job = self.store.get(job_id)
            if not job or job["status"] in TERMINAL_STATUSES:
                return
            attempt = 0
            # The handler advanced the job but it is still running upstream.
            await asyncio.sleep(self.poll_interval_seconds)

    async def wait_idle(self) -> None:
        while self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)

    async def close(self) -> None:
        for task in list(self.tasks.values()):
            task.cancel()
        for task in list(self.tasks.values()):
            with suppress(asyncio.CancelledError):
                await task
