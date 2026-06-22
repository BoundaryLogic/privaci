"""Tests for COPY OUT → COPY IN chunk pipe."""

from __future__ import annotations

import asyncio

import pytest

from privaci.stream.copy_pipe import CopyChunkPipe


@pytest.mark.asyncio
async def test_copy_chunk_pipe_streams_chunks_in_order() -> None:
    # Arrange
    pipe = CopyChunkPipe(max_queue_depth=2)
    chunks = [b"alpha", b"beta", b"gamma"]
    received: list[bytes] = []

    async def producer() -> None:
        for chunk in chunks:
            await pipe.write(chunk)
        await pipe.close()

    async def consumer() -> None:
        async for chunk in pipe:
            received.append(chunk)

    # Act
    await asyncio.gather(producer(), consumer())

    # Assert
    assert received == chunks


@pytest.mark.asyncio
async def test_copy_chunk_pipe_blocks_writer_when_queue_is_full() -> None:
    # Arrange
    pipe = CopyChunkPipe(max_queue_depth=1)
    second_write_started = asyncio.Event()
    second_write_done = asyncio.Event()

    async def writer() -> None:
        await pipe.write(b"first")
        second_write_started.set()
        await pipe.write(b"second")
        second_write_done.set()
        await pipe.close()

    writer_task = asyncio.create_task(writer())
    await asyncio.wait_for(second_write_started.wait(), timeout=1.0)
    await asyncio.sleep(0.02)

    # Assert — second write waits until the reader drains the queue.
    assert not second_write_done.is_set()
    iterator = aiter(pipe)
    assert await anext(iterator) == b"first"
    await asyncio.wait_for(second_write_done.wait(), timeout=1.0)
    assert await anext(iterator) == b"second"
    with pytest.raises(StopAsyncIteration):
        await anext(iterator)
    assert writer_task.exception() is None
