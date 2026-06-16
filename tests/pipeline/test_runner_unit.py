"""Unit tests for pipeline runner helpers."""

from __future__ import annotations

import pytest

from privaci.catalog.models import TableInfo
from privaci.config.models import Config, TableConfig
from privaci.pipeline.table_plan import _should_stream, table_strategy


def test_should_stream_defaults_to_transform() -> None:
    # Arrange
    table = TableInfo("public", "users", ())

    # Assert
    assert _should_stream(table, Config(version="1.0"))


def test_should_stream_respects_exclude_strategy() -> None:
    # Arrange
    table = TableInfo("audit", "events", ())
    config = Config(
        version="1.0",
        tables={"audit.events": TableConfig(strategy="exclude")},
    )

    # Assert
    assert not _should_stream(table, config)


@pytest.mark.parametrize("strategy", ("empty", "truncate"))
def test_should_stream_skips_empty_and_truncate_strategies(strategy: str) -> None:
    # Arrange
    table = TableInfo("audit", "events", ())
    config = Config(
        version="1.0",
        tables={"audit.events": TableConfig(strategy=strategy)},
    )

    # Assert
    assert not _should_stream(table, config)
    assert table_strategy(table, config) == strategy
