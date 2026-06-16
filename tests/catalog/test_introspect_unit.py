"""Unit tests for catalog introspection with mocked asyncpg."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from privaci.catalog.introspect import introspect_catalog
from privaci.errors import CatalogError


class _FakeRecord(dict[str, Any]):
    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)


@pytest.mark.asyncio
async def test_introspect_catalog_builds_table_metadata(mocker: Any) -> None:
    # Arrange
    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction(*_args: object, **_kwargs: object):
        yield None

    conn.transaction = _transaction
    conn.fetch.side_effect = [
        [_FakeRecord(schema_name="public", table_name="orgs", estimated_rows=10.0)],
        [
            _FakeRecord(
                schema_name="public",
                table_name="orgs",
                attnum=1,
                column_name="id",
            )
        ],
        [],
        [
            _FakeRecord(
                schema_name="public",
                table_name="orgs",
                column_name="id",
                data_type="integer",
                not_null=True,
                default_expression=None,
                identity="",
                sequence_name=None,
            )
        ],
        [
            _FakeRecord(
                schema_name="public",
                table_name="orgs",
                constraint_name="orgs_pkey",
                constraint_type="p",
                definition="PRIMARY KEY (id)",
                deferrable=False,
                initially_deferred=False,
                source_attnums=[1],
                referenced_attnums=None,
                referenced_relid=0,
                referenced_schema=None,
                referenced_table=None,
            )
        ],
        [],
        [],  # partitioned parents
        [],  # partition children
        [],  # views
        [],  # materialized views
        [],  # triggers
        [],  # rules
        [],  # publications
    ]

    # Act
    catalog = await introspect_catalog(conn)

    # Assert
    orgs = catalog.tables["public.orgs"]
    assert orgs.primary_key == ("id",)
    assert orgs.columns[0].data_type == "integer"


@pytest.mark.asyncio
async def test_introspect_maps_permission_errors(mocker: Any) -> None:
    # Arrange
    import asyncpg

    conn = AsyncMock()

    @asynccontextmanager
    async def _transaction(*_args: object, **_kwargs: object):
        yield None

    conn.transaction = _transaction
    conn.fetch.side_effect = asyncpg.PostgresError("permission denied")
    conn.fetch.side_effect.sqlstate = "42501"

    # Act & Assert
    with pytest.raises(CatalogError, match="pg_catalog"):
        await introspect_catalog(conn)
