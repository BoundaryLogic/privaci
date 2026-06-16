"""Wide ``raw_events`` and audit log row generators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams

_EVENT_ATTR_COUNT = 55


def generate_events(params: TierParams) -> dict[str, str]:
    """Generate SQL for partitioned raw events and audit log rows."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    event_rows: list[tuple[Any, ...]] = []
    columns = [
        "event_at",
        "org_id",
        "user_id",
        "event_type",
        "payload",
        *[f"attr_{idx:02d}" for idx in range(1, _EVENT_ATTR_COUNT + 1)],
    ]

    for idx in range(1, params.raw_events + 1):
        event_at = base + timedelta(hours=idx % (24 * 365))
        attrs = tuple(f"attr-{idx}-{col}" for col in range(1, _EVENT_ATTR_COUNT + 1))
        event_rows.append(
            (
                event_at,
                ((idx - 1) % params.organizations) + 1,
                ((idx - 1) % params.users) + 1,
                ("page_view", "login", "export")[idx % 3],
                f'{{"seq": {idx}}}',
                *attrs,
            )
        )

    audit_rows = [
        (
            ((idx - 1) % params.users) + 1,
            ("login", "export", "update")[idx % 3],
            f"target-{idx}",
            f'{{"idx": {idx}}}',
        )
        for idx in range(1, params.audit_events + 1)
    ]

    return {
        "public.raw_events": insert_sql("public.raw_events", columns, event_rows),
        "audit_internal.audit_log_events": insert_sql(
            "audit_internal.audit_log_events",
            ["actor_user_id", "action", "target", "payload"],
            audit_rows,
        ),
    }
