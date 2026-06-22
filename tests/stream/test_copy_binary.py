"""Tests for COPY-binary passthrough streaming."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.config.actions import FakeAction, PassthroughAction
from privaci.config.models import TableConfig
from privaci.stream.copy_binary import (
    binary_copy_passthrough_table,
    can_binary_copy_passthrough,
)


async def _stream_binary_payload(
    *_args: object,
    output: Callable[[bytes], Awaitable[None]],
    **_kwargs: object,
) -> None:
    await output(b"\x00binary")


def _users_table() -> TableInfo:
    return TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
        primary_key=("id",),
    )


def test_can_binary_copy_passthrough_when_no_column_config() -> None:
    # Arrange
    table = _users_table()

    # Assert
    assert can_binary_copy_passthrough(table, TableConfig(), last_pk_value=None)


def test_can_binary_copy_passthrough_rejects_resume_cursor() -> None:
    # Arrange
    table = _users_table()

    # Assert
    assert not can_binary_copy_passthrough(table, TableConfig(), last_pk_value=5)


def test_can_binary_copy_passthrough_rejects_row_filter() -> None:
    # Arrange
    table = _users_table()

    # Assert
    assert not can_binary_copy_passthrough(
        table,
        TableConfig(),
        last_pk_value=None,
        row_filter='"id" IN (1, 2)',
    )


@pytest.mark.asyncio
async def test_stream_table_skips_binary_copy_when_cell_post_processor_set(
    mocker: pytest.MockFixture,
) -> None:
    """Commercial JSON hooks must not use whole-table COPY passthrough."""
    from privaci.config.models import TableConfig
    from privaci.mask.engine import MaskingEngine
    from privaci.stream import table as stream_table_mod

    table = _users_table()
    engine = mocker.Mock(spec=MaskingEngine)
    engine.uses_cell_post_processing = True
    mocker.patch.object(
        stream_table_mod,
        "can_binary_copy_passthrough",
        return_value=True,
    )
    mocker.patch.object(
        stream_table_mod,
        "binary_copy_passthrough_table",
        new_callable=AsyncMock,
    )
    mocker.patch.object(
        stream_table_mod,
        "_prepare_stream_context",
        new_callable=AsyncMock,
        return_value=mocker.Mock(),
    )
    mocker.patch.object(
        stream_table_mod,
        "_seed_stream_checkpoint",
        new_callable=AsyncMock,
    )
    mocker.patch.object(
        stream_table_mod,
        "_stream_masked_batches",
        new_callable=AsyncMock,
        return_value=1,
    )
    mocker.patch.object(
        stream_table_mod,
        "_finalize_table_stream",
        new_callable=AsyncMock,
    )

    await stream_table_mod.stream_table(
        AsyncMock(),
        AsyncMock(),
        table,
        engine,
        run_id=__import__("uuid").uuid4(),
        batch_size=10,
        table_config=TableConfig(),
    )

    stream_table_mod.binary_copy_passthrough_table.assert_not_called()


def test_can_binary_copy_passthrough_rejects_masked_columns() -> None:
    # Arrange
    table = _users_table()
    table_cfg = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")}
    )

    # Assert
    assert not can_binary_copy_passthrough(table, table_cfg, last_pk_value=None)


def test_can_binary_copy_passthrough_accepts_explicit_passthrough() -> None:
    # Arrange
    table = _users_table()
    table_cfg = TableConfig(
        columns={"email": PassthroughAction(action="passthrough")},
    )

    # Assert
    assert can_binary_copy_passthrough(table, table_cfg, last_pk_value=None)


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.asyncio
async def test_binary_copy_passthrough_table_streams_whole_table(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = _users_table()
    source = AsyncMock()
    source.fetchval = AsyncMock(return_value=2)
    source.copy_from_table = AsyncMock(side_effect=_stream_binary_payload)
    target = AsyncMock()
    target.transaction = MagicMock(return_value=_FakeTransaction())
    target.copy_to_table = AsyncMock()
    mocker.patch("privaci.stream.copy_binary.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.stream.copy_binary.mark_table_done", new_callable=AsyncMock)

    # Act
    rows = await binary_copy_passthrough_table(
        source,
        target,
        table,
        uuid.uuid4(),
    )

    # Assert
    assert rows == 2
    target.copy_to_table.assert_awaited_once()
