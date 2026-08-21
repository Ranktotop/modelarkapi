from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Only connect-phase failures are retried. At that point the request never
# reached ModelArk, so repeating it cannot duplicate a paid task or an asset.
# Read/write errors are deliberately excluded: the upstream may already have
# accepted the call and a retry would bill the user twice.
RETRYABLE_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


class TransientUpstreamError(RuntimeError):
    """An upstream call failed before it reached ModelArk and may be retried."""


def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, RETRYABLE_ERRORS)


def backoff_delay(attempt: int, base_seconds: float, max_seconds: float) -> float:
    """Exponential backoff with jitter so parallel callers do not retry in lockstep."""
    delay = min(base_seconds * 2 ** (attempt - 1), max_seconds)
    return delay * (0.5 + random.random())


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    backoff_seconds: float,
    max_backoff_seconds: float,
    description: str,
) -> T:
    """Run operation, retrying connect-phase failures such as DNS outages."""
    for attempt in range(1, max(1, attempts)):
        try:
            return await operation()
        except RETRYABLE_ERRORS as exc:
            delay = backoff_delay(attempt, backoff_seconds, max_backoff_seconds)
            logger.warning(
                "%s could not connect (attempt %d/%d): %s; retrying in %.2fs",
                description,
                attempt,
                max(1, attempts),
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    return await operation()
