"""Map PostgreSQL column comments into ``pii-catalog.yaml`` documents."""

from __future__ import annotations

import re
from collections import defaultdict

import asyncpg
import yaml

from privaci.pii_catalog.models import (
    PiiCatalog,
    PiiColumnEntry,
    PiiTableEntry,
    Sensitivity,
)

_PREFIX_MAP: tuple[tuple[re.Pattern[str], Sensitivity], ...] = (
    (re.compile(r"^\s*pii\s*:", re.IGNORECASE), "pii_direct"),
    (re.compile(r"^\s*pii_direct\s*:", re.IGNORECASE), "pii_direct"),
    (re.compile(r"^\s*direct\s*:", re.IGNORECASE), "pii_direct"),
    (re.compile(r"^\s*pii_indirect\s*:", re.IGNORECASE), "pii_indirect"),
    (re.compile(r"^\s*indirect\s*:", re.IGNORECASE), "pii_indirect"),
    (re.compile(r"^\s*internal\s*:", re.IGNORECASE), "internal"),
    (re.compile(r"^\s*public\s*:", re.IGNORECASE), "public"),
)

_COMMENT_QUERY = """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    pg_catalog.col_description(c.oid, a.attnum) AS comment
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
WHERE c.relkind IN ('r', 'p')
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND n.nspname NOT IN ('pg_catalog', 'information_schema', '_privaci')
  AND pg_catalog.col_description(c.oid, a.attnum) IS NOT NULL
ORDER BY n.nspname, c.relname, a.attnum
"""


def sensitivity_from_comment(comment: str) -> Sensitivity:
    """Return the sensitivity class inferred from a column comment."""
    text = comment.strip()
    for pattern, sensitivity in _PREFIX_MAP:
        if pattern.search(text):
            return sensitivity
    return "pii_indirect"


def catalog_from_comment_rows(
    rows: list[tuple[str, str, str, str]],
) -> PiiCatalog:
    """Build a catalog from ``(schema, table, column, comment)`` tuples."""
    by_table: dict[str, list[PiiColumnEntry]] = defaultdict(list)
    for schema_name, table_name, column_name, comment in rows:
        notes = comment.strip()
        if not notes:
            continue
        table_id = f"{schema_name}.{table_name}"
        by_table[table_id].append(
            PiiColumnEntry(
                name=column_name,
                sensitivity=sensitivity_from_comment(notes),
                source="pg_comment",
                notes=notes,
            )
        )
    catalog = [
        PiiTableEntry(table=table_id, columns=columns)
        for table_id, columns in sorted(by_table.items())
    ]
    return PiiCatalog(version="1.0", catalog=catalog)


async def fetch_column_comments(
    conn: asyncpg.Connection,
) -> list[tuple[str, str, str, str]]:
    """Return column comments from the connected PostgreSQL database."""
    records = await conn.fetch(_COMMENT_QUERY)
    return [
        (
            str(row["schema_name"]),
            str(row["table_name"]),
            str(row["column_name"]),
            str(row["comment"]),
        )
        for row in records
    ]


def render_catalog_yaml(catalog: PiiCatalog) -> str:
    """Serialize a catalog to stable YAML text."""
    payload = catalog.model_dump(mode="python", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
