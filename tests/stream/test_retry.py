"""Tests for source-connection retry helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.stream.retry import with_source_retry


@pytest.mark.asyncio
async def test_with_source_retry_succeeds_on_first_attempt() -> None:
    # Arrange
    operation = AsyncMock(return_value=[{"id": 1}])

    # Act
    result = await with_source_retry(operation)

    # Assert
    assert result == [{"id": 1}]
    operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_source_retry_retries_transient_postgres_errors(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    operation = AsyncMock(
        side_effect=[
            asyncpg.PostgresConnectionError("connection lost"),
            [{"id": 1}],
        ]
    )
    sleep = mocker.patch("privaci.stream.retry.asyncio.sleep", new_callable=AsyncMock)

    # Act
    result = await with_source_retry(operation, attempts=3)

    # Assert
    assert result == [{"id": 1}]
    assert operation.await_count == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_source_retry_raises_after_exhausting_attempts() -> None:
    # Arrange
    operation = AsyncMock(side_effect=OSError("network down"))

    # Act / Assert
    with pytest.raises(OSError, match="network down"):
        await with_source_retry(operation, attempts=2)

    assert operation.await_count == 2
