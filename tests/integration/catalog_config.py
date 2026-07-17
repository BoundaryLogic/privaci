"""Shared catalog-driven config builders for integration tests."""

from __future__ import annotations

import asyncpg

from privaci.catalog import introspect_catalog
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config, ElevatedDisposition, TableConfig


def keep_only(
    catalog: CatalogResult,
    transforms: dict[str, TableConfig],
) -> dict[str, TableConfig]:
    """Build table configs that exclude every catalog table except ``transforms``.

    Args:
        catalog: Introspected source catalog.
        transforms: Table ids to include with their desired configuration.

    Returns:
        A full ``tables`` mapping suitable for :class:`Config`.
    """
    tables: dict[str, TableConfig] = {
        table_id: TableConfig(strategy="exclude")
        for table_id in catalog.tables
        if table_id not in transforms
    }
    tables.update(transforms)
    return tables


def skip_elevated_objects(catalog: CatalogResult) -> dict[str, ElevatedDisposition]:
    """Return ``skip`` dispositions for every elevated view/function in ``catalog``.

    Subset integration configs often exclude most tables; without dispositions,
    elevated Demo Corp objects would fail preflight under ``schema_mode: replicate``.
    """
    dispositions: dict[str, ElevatedDisposition] = {}
    for view in catalog.views:
        if view.kind == "view" and view.is_elevated:
            dispositions[view.identifier] = "skip"
    for function in catalog.functions:
        if function.is_elevated:
            dispositions[function.identifier] = "skip"
    return dispositions


async def config_keep_only(
    source_dsn: str,
    transforms: dict[str, TableConfig],
    **config_kwargs: object,
) -> Config:
    """Introspect ``source_dsn`` and return a config scoped to ``transforms``."""
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()
    elevated = skip_elevated_objects(catalog)
    caller_elevated = config_kwargs.pop("elevated_objects", None)
    if isinstance(caller_elevated, dict):
        elevated.update(caller_elevated)  # type: ignore[arg-type]
    return Config(
        version="1.0",
        tables=keep_only(catalog, transforms),
        elevated_objects=elevated,
        **config_kwargs,
    )
