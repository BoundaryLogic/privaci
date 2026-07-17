"""Unit tests for streaming commit-batch helpers."""

from __future__ import annotations

from privaci.catalog.models import DeferredEdge
from privaci.pipeline.streaming import _commit_batches, _multi_table_cycle_components


def test_commit_batches_one_table_each_without_cycles() -> None:
    batches = _commit_batches(("a", "b", "c"), ())

    assert batches == [("a",), ("b",), ("c",)]


def test_commit_batches_keeps_cycle_mates_together() -> None:
    components = _multi_table_cycle_components(
        (
            DeferredEdge(
                referencing_table="a",
                foreign_key_name="fk_ab",
                referenced_table="b",
            ),
        )
    )
    batches = _commit_batches(("a", "c", "b"), components)

    assert any(set(batch) == {"a", "b"} for batch in batches)
    assert ("c",) in batches
