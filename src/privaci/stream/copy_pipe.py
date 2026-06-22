"""Bounded byte pipe between asyncpg COPY OUT and COPY IN."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

# Postgres COPY chunks are typically well under 512 KiB; cap in-flight chunks
# so passthrough tables never buffer the whole relation in RAM.
_DEFAULT_QUEUE_DEPTH = 16


class CopyChunkPipe:
    """Async byte pipe from a COPY OUT writer to a COPY IN reader.

    ``write`` is passed to ``Connection.copy_from_table(..., output=...)``.
    The pipe itself is passed to ``Connection.copy_to_table(..., source=...)``.
    A full queue blocks the source COPY, applying backpressure.
    """

    __slots__ = ("_closed", "_queue")

    def __init__(self, *, max_queue_depth: int = _DEFAULT_QUEUE_DEPTH) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(
            maxsize=max_queue_depth
        )
        self._closed = False

    async def write(self, chunk: bytes) -> None:
        """Receive one COPY OUT chunk; await when the queue is full."""
        if self._closed:
            msg = "CopyChunkPipe is closed"
            raise RuntimeError(msg)
        await self._queue.put(chunk)

    async def close(self) -> None:
        """Signal end-of-stream to the COPY IN reader."""
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._iter_chunks()

    async def _iter_chunks(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk
