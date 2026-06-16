"""Retry helpers for transient source-connection failures during streaming."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import asyncpg

logger = logging.getLogger(__name__)

_DEFAULT_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 0.5

_T = TypeVar("_T")


async def with_source_retry(
    operation: Callable[[], Awaitable[_T]],
    *,
    attempts: int = _DEFAULT_ATTEMPTS,
    base_delay_seconds: float = _BASE_DELAY_SECONDS,
) -> _T:
    """Run ``operation`` with exponential backoff on transient source errors.

    Args:
        operation: Async callable to execute (typically a batch fetch).
        attempts: Maximum number of tries before propagating the error.
        base_delay_seconds: Initial backoff delay, doubled after each failure.

    Returns:
        The result of a successful ``operation`` invocation.

    Raises:
        asyncpg.PostgresError: When all attempts are exhausted.
        OSError: When all attempts are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except (asyncpg.PostgresError, OSError, ConnectionError) as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Source operation failed; retrying",
                extra={"attempt": attempt, "delay_seconds": delay},
            )
            await asyncio.sleep(delay)
    if last_error is None:
        msg = "source retry loop exited without executing operation"
        raise RuntimeError(msg)
    raise last_error
