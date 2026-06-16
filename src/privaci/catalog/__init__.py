"""PostgreSQL catalog introspection and FK graph."""

from __future__ import annotations

from privaci.catalog.introspect import introspect_catalog
from privaci.catalog.models import (
    CatalogResult,
    CatalogWarning,
    ColumnInfo,
    DeferredEdge,
    ForeignKeyInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
    ViewInfo,
    parse_table_id,
    table_id,
)
from privaci.catalog.snapshot import (
    canonical_snapshot_json,
    persist_source_schema_snapshot,
)

__all__ = [
    "CatalogResult",
    "CatalogWarning",
    "ColumnInfo",
    "DeferredEdge",
    "ForeignKeyInfo",
    "LoadLayer",
    "LoadPlan",
    "TableInfo",
    "ViewInfo",
    "canonical_snapshot_json",
    "introspect_catalog",
    "parse_table_id",
    "persist_source_schema_snapshot",
    "table_id",
]
