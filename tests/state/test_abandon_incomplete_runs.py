"""Unit tests for abandon_incomplete_runs."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from privaci.state.resume import abandon_incomplete_runs


@pytest.mark.asyncio
async def test_abandon_incomplete_runs_finishes_each(mocker: MockerFixture) -> None:
    # Arrange
    run_a = uuid.uuid4()
    run_b = uuid.uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[{"run_id": run_a}, {"run_id": run_b}])
    finish = mocker.patch(
        "privaci.state.resume.finish_run",
        new=AsyncMock(),
    )

    # Act
    abandoned = await abandon_incomplete_runs(conn)

    # Assert
    assert abandoned == 2
    assert finish.await_count == 2
