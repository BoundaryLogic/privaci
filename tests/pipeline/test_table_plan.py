"""Tests for per-table streaming disposition planning."""

from __future__ import annotations

import pytest

from privaci.catalog.models import TableInfo
from privaci.config.models import Config, TableConfig
from privaci.pipeline.table_plan import TableAction, _should_stream, plan_table
from privaci.state.models import CheckpointStatus
from privaci.state.resume import TableCheckpoint


def test_plan_table_streams_by_default() -> None:
    # Arrange
    table = TableInfo("public", "users", ())

    # Act & Assert
    assert plan_table(table, Config(version="1.0"), None) is TableAction.STREAM


def test_plan_table_skips_done_checkpoint() -> None:
    # Arrange
    table = TableInfo("public", "users", (), primary_key=("id",))
    checkpoint = TableCheckpoint(
        schema_name="public",
        table_name="users",
        status=CheckpointStatus.DONE,
        last_pk_value="1",
        rows_processed=10,
    )

    # Act & Assert
    assert plan_table(table, Config(version="1.0"), checkpoint) is TableAction.SKIP_DONE


@pytest.mark.parametrize("strategy", ("empty", "truncate"))
def test_plan_table_finalizes_empty_strategies(strategy: str) -> None:
    # Arrange
    table = TableInfo("audit", "events", ())
    config = Config(
        version="1.0",
        tables={"audit.events": TableConfig(strategy=strategy)},
    )

    # Act & Assert
    assert plan_table(table, config, None) is TableAction.FINALIZE_EMPTY
    assert not _should_stream(table, config)
