"""Fetch catalog objects that are never replicated (rules, publications)."""

from __future__ import annotations

import asyncpg

from privaci.catalog.models import SkippedObjectInfo
from privaci.catalog.queries import PUBLICATIONS_SQL, RULES_SQL


async def fetch_skipped_objects(
    conn: asyncpg.Connection,
) -> tuple[SkippedObjectInfo, ...]:
    """Return rules and publications that are never replicated."""
    objects: list[SkippedObjectInfo] = []
    objects.extend(await _fetch_rule_objects(conn))
    objects.extend(await _fetch_publication_objects(conn))
    return tuple(
        sorted(
            objects,
            key=lambda item: (item.schema_name, item.kind, item.object_name),
        )
    )


async def _fetch_rule_objects(conn: asyncpg.Connection) -> list[SkippedObjectInfo]:
    return [
        SkippedObjectInfo(
            schema_name=row["schema_name"],
            object_name=row["rule_name"],
            kind="rule",
            parent_table=row["table_name"],
        )
        for row in await conn.fetch(RULES_SQL)
    ]


async def _fetch_publication_objects(
    conn: asyncpg.Connection,
) -> list[SkippedObjectInfo]:
    return [
        SkippedObjectInfo(
            schema_name="",
            object_name=row["publication_name"],
            kind="publication",
        )
        for row in await conn.fetch(PUBLICATIONS_SQL)
    ]
