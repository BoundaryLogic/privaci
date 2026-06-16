"""Integration test for COPY-binary round-trip spike."""

from __future__ import annotations

import pytest

from privaci.spikes.copy_binary import run_copy_binary_spike


@pytest.mark.integration
@pytest.mark.spike
async def test_copy_binary_roundtrip(
    postgres_available: None,
    source_dsn: str,
    target_dsn: str,
) -> None:
    # Act
    result = await run_copy_binary_spike(source_dsn, target_dsn)

    # Assert
    assert result.source_rows >= 3
    assert result.passed
