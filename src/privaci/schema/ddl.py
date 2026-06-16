"""DDL emission from catalog ``TableInfo`` metadata."""

from __future__ import annotations

from privaci.catalog.identifiers import qualify, quote_pg_identifier
from privaci.catalog.models import ColumnInfo, ForeignKeyInfo, TableInfo


def emit_create_sequence(sequence_name: str) -> str:
    """Emit ``CREATE SEQUENCE IF NOT EXISTS`` for a qualified sequence name.

    ``sequence_name`` is the output of ``pg_get_serial_sequence`` — an
    already-quoted, ``regclass``-ready qualified identifier (the same string
    passed directly to ``nextval``/``setval`` elsewhere). It is embedded as-is
    rather than split on ``.`` and re-quoted, which corrupted any schema or
    sequence name legitimately containing a dot.
    """
    return f"CREATE SEQUENCE IF NOT EXISTS {sequence_name}"


def emit_create_schema(schema_name: str) -> str:
    """Return ``CREATE SCHEMA IF NOT EXISTS`` for one schema."""
    return f"CREATE SCHEMA IF NOT EXISTS {quote_pg_identifier(schema_name)}"


def emit_create_table(table: TableInfo) -> str:
    """Emit ``CREATE TABLE IF NOT EXISTS`` with columns, PK, and checks."""
    body = _table_body(table)
    suffix = ""
    if table.is_partitioned and table.partition_key_def:
        suffix = f" PARTITION BY {table.partition_key_def}"
    return (
        f"CREATE TABLE IF NOT EXISTS {table.sql_ref} (\n" f"    {body}\n" f"){suffix}"
    )


def emit_create_partition_child(table: TableInfo, parent: TableInfo) -> str:
    """Emit ``CREATE TABLE ... PARTITION OF`` for one partition child."""
    bound = table.partition_bound or ""
    return (
        f"CREATE TABLE IF NOT EXISTS {table.sql_ref} "
        f"PARTITION OF {parent.sql_ref} {bound}"
    )


def _table_body(table: TableInfo) -> str:
    lines = [_column_line(column) for column in table.columns]
    if table.primary_key:
        pk_cols = ", ".join(quote_pg_identifier(name) for name in table.primary_key)
        lines.append(f"PRIMARY KEY ({pk_cols})")
    for check in table.check_constraints:
        constraint = quote_pg_identifier(check.name)
        lines.append(f"CONSTRAINT {constraint} CHECK ({check.definition})")
    return ",\n    ".join(lines)


def emit_unique_indexes(table: TableInfo, *, replicate_all: bool) -> list[str]:
    """Return ``CREATE UNIQUE INDEX`` statements for a table."""
    statements: list[str] = []
    for index in table.indexes:
        if replicate_all or index.is_unique:
            statements.append(index.definition)
    return statements


def emit_foreign_key(table: TableInfo, fk: ForeignKeyInfo) -> str:
    """Emit ``ALTER TABLE ... ADD CONSTRAINT`` for one FK."""
    source = ", ".join(quote_pg_identifier(col) for col in fk.source_columns)
    target = ", ".join(quote_pg_identifier(col) for col in fk.referenced_columns)
    defer = ""
    if fk.deferrable:
        defer = " DEFERRABLE"
        if fk.initially_deferred:
            defer += " INITIALLY DEFERRED"
        else:
            defer += " INITIALLY IMMEDIATE"
    parent_ref = qualify(fk.referenced_schema, fk.referenced_table)
    constraint = quote_pg_identifier(fk.name)
    return (
        f"ALTER TABLE {table.sql_ref} "
        f"ADD CONSTRAINT {constraint} FOREIGN KEY ({source}) "
        f"REFERENCES {parent_ref} ({target}) "
        f"ON DELETE {fk.on_delete} ON UPDATE {fk.on_update}{defer}"
    )


def _column_line(column: ColumnInfo) -> str:
    parts = [quote_pg_identifier(column.name), column.data_type]
    if column.is_identity:
        generation = (column.identity_generation or "BY DEFAULT").upper()
        parts.append(f"GENERATED {generation} AS IDENTITY")
    elif column.uses_serial and column.sequence_name:
        if column.not_null:
            parts.append("NOT NULL")
        parts.append(f"DEFAULT nextval('{column.sequence_name}'::regclass)")
    else:
        if column.not_null:
            parts.append("NOT NULL")
        if column.default_expression:
            parts.append(f"DEFAULT {column.default_expression}")
    return " ".join(parts)
