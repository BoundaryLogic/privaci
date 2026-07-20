"""Fetch user triggers for optional post-data replication."""

from __future__ import annotations

import asyncpg

from privaci.catalog.models import TriggerInfo
from privaci.catalog.queries import TRIGGERS_SQL


async def fetch_triggers(conn: asyncpg.Connection) -> tuple[TriggerInfo, ...]:
    """Return user triggers with create definitions for post-data DDL."""
    triggers = [
        TriggerInfo(
            schema_name=row["schema_name"],
            table_name=row["table_name"],
            trigger_name=row["trigger_name"],
            create_sql=row["create_sql"],
            function_identity=row["function_identity"],
        )
        for row in await conn.fetch(TRIGGERS_SQL)
    ]
    return tuple(
        sorted(
            triggers,
            key=lambda item: (item.schema_name, item.table_name, item.trigger_name),
        )
    )
