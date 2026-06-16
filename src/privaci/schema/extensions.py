"""Map catalog column types to required Postgres extensions."""

from __future__ import annotations

from privaci.catalog.models import CatalogResult

# Column types that require a CREATE EXTENSION on the target before DDL.
_TYPE_EXTENSIONS: dict[str, str] = {
    "ltree": "ltree",
    "ltree[]": "ltree",
}


def required_extensions(catalog: CatalogResult) -> list[str]:
    """Return sorted extension names needed by in-scope catalog column types."""
    found: set[str] = set()
    for table in catalog.tables.values():
        for column in table.columns:
            extension = _TYPE_EXTENSIONS.get(column.data_type.strip().lower())
            if extension is not None:
                found.add(extension)
    return sorted(found)


def emit_create_extension(extension_name: str) -> str:
    """Return ``CREATE EXTENSION IF NOT EXISTS`` for one extension."""
    return f"CREATE EXTENSION IF NOT EXISTS {extension_name}"
