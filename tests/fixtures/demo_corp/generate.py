"""CLI to emit deterministic Demo Corp SQL fixtures."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tests.fixtures.demo_corp.providers import (
    generate_clinical_data,
    generate_events,
    generate_org_data,
    generate_ticket_data,
    generate_user_data,
    generate_visit_rows,
)
from tests.fixtures.demo_corp.schema import ddl_sections
from tests.fixtures.demo_corp.seed import reset_seed
from tests.fixtures.demo_corp.tiers import TierName, resolve_tier

logger = logging.getLogger(__name__)

_DEFAULT_OUT = Path("tests/fixtures/sql/demo-corp")


def build_data_sql(tier: str, *, scale: int) -> str:
    """Generate all INSERT/UPDATE statements for a tier."""
    params = resolve_tier(tier, scale=scale)
    reset_seed()

    sections: list[str] = ["-- Demo Corp seed data (generated; do not edit by hand)"]
    org_data = generate_org_data(params)
    user_data = generate_user_data(params)
    clinical_data = generate_clinical_data(params)
    ticket_data = generate_ticket_data(params)
    visit_data = generate_visit_rows(params)
    event_data = generate_events(params)

    ordered_keys = [
        "public.organizations",
        "public.users",
        "public.subscriptions",
        "public.user_addresses",
        "public.user_payment_methods",
        "public.employees",
        "public.tickets",
        "clinical.providers",
        "clinical.patients",
        "clinical.patient_visits",
        "clinical.prescriptions",
        "clinical.patient_documents",
        "public.ticket_messages",
        "public.comments",
        "public.invoices",
        "public.invoice_line_items",
        "public.raw_events",
        "public.geo_locations",
        "auth.sessions",
        "auth.api_keys",
        "audit_internal.audit_log_events",
    ]

    payload = {
        **org_data,
        **user_data,
        **clinical_data,
        **ticket_data,
        **visit_data,
        **event_data,
    }
    for key in ordered_keys:
        if key in payload:
            sections.append(payload[key])

    sections.append(org_data["public.organizations_cycle_close"])
    sections.append("-- Refresh planner statistics after load\nANALYZE;\n")
    return "\n".join(sections) + "\n"


def write_fixture_sql(out_dir: Path, tier: str, *, scale: int) -> list[Path]:
    """Write schema and data SQL files to ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("*.sql"):
        existing.unlink()

    written: list[Path] = []
    for filename, sql in ddl_sections():
        path = out_dir / filename
        path.write_text(sql, encoding="utf-8")
        written.append(path)

    data_path = out_dir / "09_seed_data.sql"
    data_path.write_text(build_data_sql(tier, scale=scale), encoding="utf-8")
    written.append(data_path)
    return written


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args and emit fixture SQL."""
    parser = argparse.ArgumentParser(description="Generate Demo Corp SQL fixtures")
    parser.add_argument(
        "--tier",
        choices=[t.value for t in TierName],
        default=TierName.MINI.value,
        help="Fixture tier (mini is committed for CI; demo is full scale)",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="Multiply demo-tier counts (stress uses demo x scale)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output directory for SQL files",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    paths = write_fixture_sql(args.out, args.tier, scale=args.scale)
    for path in paths:
        logger.info("Wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
