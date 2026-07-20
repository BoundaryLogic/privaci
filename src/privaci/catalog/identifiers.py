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
    from privaci.catalog.models import (
        FunctionInfo,
        SkippedObjectInfo,
        TableInfo,
        TriggerInfo,
        ViewInfo,
    )


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


def assert_safe_identifiers(
    tables: dict[str, TableInfo],
    *,
    views: tuple[ViewInfo, ...] = (),
    functions: tuple[FunctionInfo, ...] = (),
    triggers: tuple[TriggerInfo, ...] = (),
    skipped_objects: tuple[SkippedObjectInfo, ...] = (),
) -> None:
    """Reject NUL/control-char names at introspection time, before any SQL runs.

    Validates schema/table/column names plus views, functions, triggers,
    sequences, indexes, and constraint names so a hostile catalog fails loud
    during pre-flight rather than at the first dynamically-built query.

    Raises:
        CatalogError: If any identifier contains a NUL/control character.
    """
    for table in tables.values():
        quote_pg_identifier(table.schema_name)
        quote_pg_identifier(table.table_name)
        for column in table.columns:
            quote_pg_identifier(column.name)
            if column.sequence_name:
                _assert_sequence_name(column.sequence_name)
        for check in table.check_constraints:
            quote_pg_identifier(check.name)
        for foreign_key in table.foreign_keys:
            quote_pg_identifier(foreign_key.name)
        for index in table.indexes:
            quote_pg_identifier(index.name)
    for view in views:
        quote_pg_identifier(view.schema_name)
        quote_pg_identifier(view.view_name)
    for function in functions:
        quote_pg_identifier(function.schema_name)
        quote_pg_identifier(function.function_name)
    for trigger in triggers:
        quote_pg_identifier(trigger.schema_name)
        quote_pg_identifier(trigger.table_name)
        quote_pg_identifier(trigger.trigger_name)
    for skipped in skipped_objects:
        if skipped.schema_name:
            quote_pg_identifier(skipped.schema_name)
        if skipped.object_name:
            quote_pg_identifier(skipped.object_name)


def _assert_sequence_name(sequence_name: str) -> None:
    """Validate a schema-qualified sequence name from pg_get_serial_sequence."""
    if "." in sequence_name:
        schema_name, _, object_name = sequence_name.partition(".")
        quote_pg_identifier(schema_name.strip('"'))
        quote_pg_identifier(object_name.strip('"'))
        return
    quote_pg_identifier(sequence_name.strip('"'))
