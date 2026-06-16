"""Integration test for deferred cyclic FK spike."""

from __future__ import annotations

import pytest

from privaci.spikes.cyclic_fk import run_cyclic_fk_spike


@pytest.mark.integration
@pytest.mark.spike
async def test_cyclic_fk_deferred_load(
    postgres_available: None,
    source_dsn: str,
) -> None:
    # Act
    result = await run_cyclic_fk_spike(source_dsn)

    # Assert
    assert result.passed
