"""Integration test for COPY-binary round-trip spike."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from privaci.spikes.copy_binary import run_copy_binary_spike

_SPIKE_SQL = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sql"
    / "spikes"
    / "01_copy_roundtrip.sql"
)


@pytest.mark.integration
@pytest.mark.spike
async def test_copy_binary_roundtrip(
    postgres_available: None,
    source_dsn: str,
    target_dsn: str,
) -> None:
    # Arrange — seed source even if Demo Corp wiped public earlier in the session.
    source = await asyncpg.connect(source_dsn)
    try:
        await source.execute(_SPIKE_SQL.read_text(encoding="utf-8"))
    finally:
        await source.close()

    # Act
    result = await run_copy_binary_spike(source_dsn, target_dsn)

    # Assert
    assert result.source_rows >= 3
    assert result.passed
