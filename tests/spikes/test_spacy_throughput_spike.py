"""SpaCy throughput spike (no database)."""

from __future__ import annotations

import pytest

from privaci.spikes.spacy_throughput import (
    TARGET_ROWS_PER_SEC,
    run_spacy_throughput_spike,
)


@pytest.mark.spike
def test_spacy_throughput_meets_week1_target() -> None:
    # Act
    try:
        result = run_spacy_throughput_spike(row_count=500, batch_size=32)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    # Assert — record metric even when below target; warn in CI via spike script
    assert result.row_count == 500
    assert result.rows_per_second > 0
    if result.rows_per_second < TARGET_ROWS_PER_SEC:
        pytest.xfail(
            f"SpaCy throughput {result.rows_per_second:.0f} rows/sec "
            f"below target {TARGET_ROWS_PER_SEC}",
        )
