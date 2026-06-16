"""Support ticket row generators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.fixtures.demo_corp.providers.messages import narrative_ticket_body
from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams


def generate_ticket_data(params: TierParams) -> dict[str, str]:
    """Generate SQL for tickets, messages, and polymorphic comments."""
    ticket_rows = [
        (
            ((idx - 1) % params.organizations) + 1,
            ((idx - 1) % params.users) + 1,
            ((idx) % params.users) + 1,
            f"Support request #{idx}",
            ("open", "pending", "closed")[idx % 3],
            ("low", "normal", "high")[idx % 3],
        )
        for idx in range(1, params.tickets + 1)
    ]

    message_rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.ticket_messages + 1):
        ticket_id = ((idx - 1) % params.tickets) + 1
        author_id = ((idx - 1) % params.users) + 1
        patient_idx = ((idx - 1) % params.patients) + 1
        body = narrative_ticket_body(
            patient_name=f"Pat{patient_idx} Patient{patient_idx}",
            mrn=f"MRN{patient_idx:08d}",
            visit_date="2024-06-15",
            author_name=f"First{author_id} Last{author_id}",
        )
        posted = datetime(2024, 6, 1, tzinfo=UTC) + timedelta(minutes=idx)
        message_rows.append((ticket_id, author_id, body, posted))

    comment_rows = [
        (
            ("Ticket", "Patient", "Organization")[idx % 3],
            ((idx * 13) % max(params.patients, 1)) + 1,
            ((idx - 1) % params.users) + 1,
            f"Comment body {idx} on polymorphic target",
        )
        for idx in range(1, params.comments + 1)
    ]

    return {
        "public.tickets": insert_sql(
            "public.tickets",
            [
                "org_id",
                "reporter_user_id",
                "assigned_to_user_id",
                "subject",
                "status",
                "priority",
            ],
            ticket_rows,
        ),
        "public.ticket_messages": insert_sql(
            "public.ticket_messages",
            ["ticket_id", "author_user_id", "body", "posted_at"],
            message_rows,
        ),
        "public.comments": insert_sql(
            "public.comments",
            ["commentable_type", "commentable_id", "author_user_id", "body"],
            comment_rows,
        ),
    }
