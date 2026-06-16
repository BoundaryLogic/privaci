"""Organization and billing row generators."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tests.fixtures.demo_corp.seed import fixture_email
from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams


def generate_org_data(params: TierParams) -> dict[str, str]:
    """Generate SQL for organizations, subscriptions, and invoices."""
    org_rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.organizations + 1):
        org_rows.append(
            (
                f"Org {idx}",
                f"{idx % 100:02d}-{idx:07d}",
                fixture_email("billing", idx),
                None,
                None,
            )
        )

    sub_rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.subscriptions + 1):
        sub_rows.append(
            (
                ((idx - 1) % params.organizations) + 1,
                ("starter", "team", "business")[idx % 3],
                date(2023, 1, 1) + timedelta(days=idx),
                None,
            )
        )

    invoice_rows: list[tuple[Any, ...]] = []
    line_rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.invoices + 1):
        sub_id = ((idx - 1) % params.subscriptions) + 1
        start = date(2024, 1, 1) + timedelta(days=30 * (idx % 12))
        end = start + timedelta(days=30)
        invoice_rows.append((sub_id, start, end, 9900 + (idx * 100)))
        lines_per = max(1, params.invoice_line_items // max(params.invoices, 1))
        for line_no in range(1, lines_per + 1):
            if len(line_rows) >= params.invoice_line_items:
                break
            line_rows.append((idx, line_no, f"Line {line_no}", 1000 + line_no))

    geo_rows = [
        (f"Region {idx}", f"us.east.{idx}")
        for idx in range(1, min(20, params.organizations) + 1)
    ]

    return {
        "public.organizations": insert_sql(
            "public.organizations",
            ["name", "ein", "billing_email", "owner_user_id", "primary_user_id"],
            org_rows,
        ),
        "public.subscriptions": insert_sql(
            "public.subscriptions",
            ["org_id", "plan", "started_at", "billing_address_id"],
            sub_rows,
        ),
        "public.invoices": insert_sql(
            "public.invoices",
            ["subscription_id", "period_start", "period_end", "total_cents"],
            invoice_rows,
        ),
        "public.invoice_line_items": insert_sql(
            "public.invoice_line_items",
            ["invoice_id", "line_no", "description", "amount_cents"],
            line_rows,
        ),
        "public.geo_locations": insert_sql(
            "public.geo_locations",
            ["name", "region_path"],
            geo_rows,
        ),
        "public.organizations_cycle_close": _cycle_close_sql(params),
    }


def _cycle_close_sql(params: TierParams) -> str:
    # TierParams.users is an int from tier presets, not external input.
    users = params.users
    return f"""\
-- Close organizations <-> users deferred FK cycle
UPDATE public.organizations o
SET owner_user_id = ((o.id - 1) % {users}) + 1,
    primary_user_id = (o.id % {users}) + 1;
"""  # noqa: S608
