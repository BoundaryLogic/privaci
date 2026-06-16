"""Safe PostgreSQL identifier quoting for dynamically built SQL.

Identifiers (schema, table, column names) cannot be passed as query parameters,
so any SQL that names a catalog object must embed the identifier as text. Those
names come from introspecting an untrusted source/target database, so they are
treated as untrusted input: this module is the single, mandatory mechanism for
rendering them safely. Naive ``f'"{name}"'`` interpolation is an injection vector
because an identifier containing a double-quote escapes the quoted token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from privaci.errors import CatalogError

if TYPE_CHECKING:
    from privaci.catalog.models import TableInfo


def quote_pg_identifier(name: str) -> str:
    """Return ``name`` as a safely double-quoted PostgreSQL identifier.

    Doubles every embedded double-quote (the PostgreSQL escaping rule, ``"`` →
    ``""``) and rejects empty identifiers or identifiers containing NUL/control
    characters, which are never valid in a real object name and would otherwise
    allow SQL injection through a hostile catalog.

    Args:
        name: A schema, table, or column name from catalog introspection.

    Returns:
        The identifier wrapped in double quotes, safe to embed in SQL.

    Raises:
        CatalogError: If ``name`` is empty or contains a NUL/control character.

    Example:
        >>> quote_pg_identifier('user"; DROP')
        '"user""; DROP"'
    """
    if not name:
        raise CatalogError(
            "Quoting a SQL identifier",
            cause="Encountered an empty identifier from the catalog.",
            remediation="Verify the source schema; report this if it persists.",
        )
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in name):
        raise CatalogError(
            "Quoting a SQL identifier",
            cause=f"Identifier {name!r} contains a control character.",
            remediation="Rename the offending object in the source database.",
        )
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def qualify(schema_name: str, object_name: str) -> str:
    """Return a safely-quoted ``"schema"."object"`` reference."""
    return f"{quote_pg_identifier(schema_name)}.{quote_pg_identifier(object_name)}"


def assert_safe_identifiers(tables: dict[str, TableInfo]) -> None:
    """Reject NUL/control-char names at introspection time, before any SQL runs.

    Validates every schema, table, and column name so a hostile catalog fails
    loud during pre-flight rather than at the first dynamically-built query.

    Raises:
        CatalogError: If any identifier contains a NUL/control character.
    """
    for table in tables.values():
        quote_pg_identifier(table.schema_name)
        quote_pg_identifier(table.table_name)
        for column in table.columns:
            quote_pg_identifier(column.name)
