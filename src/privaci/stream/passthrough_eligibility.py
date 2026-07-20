"""Binary COPY eligibility checks used by the streaming path."""

from __future__ import annotations

from typing import Any

import asyncpg

from privaci.catalog.models import TableInfo
from privaci.config.actions import PassthroughAction
from privaci.config.conditional import table_has_when
from privaci.config.models import Config, TableConfig
from privaci.schema.assume_existing import (
    binary_copy_columns_match,
    fetch_target_columns,
)
from privaci.stream.coerce import table_needs_text_fallback


def table_is_passthrough_candidate(
    table: TableInfo,
    table_cfg: TableConfig,
    *,
    last_pk_value: Any | None = None,
    row_filter: str | None = None,
) -> bool:
    """Return whether the table would use whole-table binary COPY if eligible."""
    if row_filter is not None or last_pk_value is not None:
        return False
    if table_has_when(table_cfg.columns):
        return False
    column_types = {column.name: column.data_type for column in table.columns}
    if table_needs_text_fallback(column_types):
        return False
    if any(
        column.is_identity and column.identity_generation == "ALWAYS"
        for column in table.columns
    ):
        return False
    if not table_cfg.columns:
        return True
    return all(
        isinstance(action, PassthroughAction) for action in table_cfg.columns.values()
    )


async def is_binary_copy_eligible(
    conn: asyncpg.Connection,
    table: TableInfo,
    table_cfg: TableConfig,
    config: Config,
    *,
    last_pk_value: Any | None,
    row_filter: str | None = None,
) -> bool:
    """Return whether binary COPY may be used for this table under config policy."""
    if config.passthrough_copy == "batch":
        return False
    if not table_is_passthrough_candidate(
        table,
        table_cfg,
        last_pk_value=last_pk_value,
        row_filter=row_filter,
    ):
        return False
    target_cols = await fetch_target_columns(conn, table.schema_name, table.table_name)
    return binary_copy_columns_match(table, target_cols)
