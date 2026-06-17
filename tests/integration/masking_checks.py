"""Shared masking verification helpers for Postgres integration tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import asyncpg

from privaci.config.models import Config
from privaci.mask.ner import mask_entities_in_text
from privaci.verify.models import Verdict, VerifyReport
from privaci.verify.runner import run_verification
from tests.fixtures.constants import (
    DEMO_CORP_FORBIDDEN_CARD_NUMBERS,
    DEMO_CORP_FORBIDDEN_EINS,
    DEMO_CORP_FORBIDDEN_EMAILS,
    DEMO_CORP_FORBIDDEN_FIRST_NAMES,
    DEMO_CORP_FORBIDDEN_INSURANCE_IDS,
    DEMO_CORP_FORBIDDEN_MRNS,
    DEMO_CORP_FORBIDDEN_ORG_NAMES,
    DEMO_CORP_FORBIDDEN_PASSWORD_HASHES,
    DEMO_CORP_FORBIDDEN_PHONES,
    DEMO_CORP_FORBIDDEN_SSNS,
    DEMO_CORP_HASH_HEX,
    DEMO_CORP_MASKED_EIN_PATTERN,
    DEMO_CORP_STATIC_PASSWORD,
    TEST_SALT,
)
from tests.integration.assertions import assert_no_pii_present, fetch_column_values
from tests.integration.spacy_requirements import require_spacy_ner, spacy_ner_available

_VERIFY_SAMPLE_SIZE = 500


@dataclass(frozen=True, slots=True)
class LeakProbe:
    """One column checked for surviving source values."""

    table: str
    column: str
    forbidden: tuple[str, ...]


DEMO_CORP_LEAK_PROBES: tuple[LeakProbe, ...] = (
    LeakProbe("public.users", "email", DEMO_CORP_FORBIDDEN_EMAILS),
    LeakProbe("public.users", "phone", DEMO_CORP_FORBIDDEN_PHONES),
    LeakProbe("public.users", "ssn", DEMO_CORP_FORBIDDEN_SSNS),
    LeakProbe("public.users", "first_name", DEMO_CORP_FORBIDDEN_FIRST_NAMES),
    LeakProbe("public.users", "password_hash", DEMO_CORP_FORBIDDEN_PASSWORD_HASHES),
    LeakProbe("public.organizations", "billing_email", DEMO_CORP_FORBIDDEN_EMAILS),
    LeakProbe("public.organizations", "name", DEMO_CORP_FORBIDDEN_ORG_NAMES),
    LeakProbe("public.organizations", "ein", DEMO_CORP_FORBIDDEN_EINS),
    LeakProbe("clinical.patients", "email", DEMO_CORP_FORBIDDEN_EMAILS),
    LeakProbe("clinical.patients", "ssn", DEMO_CORP_FORBIDDEN_SSNS),
    LeakProbe("clinical.patients", "mrn", DEMO_CORP_FORBIDDEN_MRNS),
    LeakProbe(
        "clinical.patients",
        "insurance_member_id",
        DEMO_CORP_FORBIDDEN_INSURANCE_IDS,
    ),
    LeakProbe("public.user_payment_methods", "cvv", ("001", "002", "003")),
    LeakProbe(
        "public.user_payment_methods",
        "card_number",
        DEMO_CORP_FORBIDDEN_CARD_NUMBERS,
    ),
)


async def assert_demo_corp_leak_probes(conn: asyncpg.Connection) -> dict[str, int]:
    """Assert configured seed values/phrases did not survive masking."""
    passed = 0
    for probe in DEMO_CORP_LEAK_PROBES:
        await assert_no_pii_present(
            conn,
            probe.table,
            probe.column,
            list(probe.forbidden),
        )
        passed += 1
    return {"probes_run": passed, "probes_passed": passed}


async def assert_demo_corp_ner_columns_changed(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
) -> None:
    """NER-masked text columns must differ from source."""
    require_spacy_ner()
    await _assert_single_pk_column_changed(
        source,
        target,
        "public.ticket_messages",
        "body",
    )
    await _assert_composite_pk_column_changed(
        source,
        target,
        "clinical.patient_visits",
        ("id", "region_code"),
        "visit_notes",
    )


async def assert_demo_corp_action_shapes(conn: asyncpg.Connection) -> None:
    """Assert masked columns match action-type output shapes on samples."""
    password_hashes = await fetch_column_values(
        conn, "public.users", "password_hash", limit=20
    )
    assert password_hashes
    assert all(value == DEMO_CORP_STATIC_PASSWORD for value in password_hashes)

    cvvs = await fetch_column_values(
        conn, "public.user_payment_methods", "cvv", limit=20
    )
    assert cvvs
    assert all(DEMO_CORP_HASH_HEX.match(str(value)) for value in cvvs)
    assert not any(value in {"001", "002", "003"} for value in cvvs)

    mrns = await fetch_column_values(conn, "clinical.patients", "mrn", limit=20)
    assert mrns
    assert all(DEMO_CORP_HASH_HEX.match(str(value)) for value in mrns)
    assert not any(str(value).startswith("MRN0000000") for value in mrns)

    eins = await fetch_column_values(conn, "public.organizations", "ein", limit=20)
    assert eins
    assert all(DEMO_CORP_MASKED_EIN_PATTERN.match(str(value)) for value in eins)
    assert not any(value in DEMO_CORP_FORBIDDEN_EINS for value in eins)

    emails = await fetch_column_values(conn, "public.users", "email", limit=20)
    assert emails
    assert all("@" in str(value) for value in emails)


async def assert_demo_corp_passthrough_unchanged(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
) -> None:
    """Passthrough columns must copy source bytes unchanged."""
    source_blob = await source.fetchval("""
        SELECT document_blob
        FROM clinical.patient_documents
        WHERE document_blob IS NOT NULL
        LIMIT 1
        """)
    target_blob = await target.fetchval("""
        SELECT document_blob
        FROM clinical.patient_documents
        WHERE document_blob IS NOT NULL
        LIMIT 1
        """)
    assert source_blob is not None
    assert target_blob == source_blob


async def run_demo_corp_verification(
    *,
    config: Config,
    source_dsn: str,
    target_dsn: str,
) -> VerifyReport:
    """Run value-free verify and fail on any FAIL verdict."""
    require_spacy_ner()
    report = await run_verification(
        config=config,
        source_dsn=source_dsn,
        target_dsn=target_dsn,
        sample_size=_VERIFY_SAMPLE_SIZE,
    )
    if report.failed:
        detail = "; ".join(
            f"{item.target}: {item.detail}" for item in report.failed[:5]
        )
        msg = f"Masking verification failed ({len(report.failed)} check(s)): {detail}"
        raise AssertionError(msg)
    return report


def verification_summary(report: VerifyReport) -> dict[str, Any]:
    """Value-free summary suitable for capability reports."""
    counts = report.counts()
    masked_checks = [r for r in report.results if r.check == "column.change_rate"]
    actionable = report.failed
    failure_samples = [
        {"target": item.target, "check": item.check, "detail": item.detail}
        for item in actionable[:8]
    ]
    return {
        "pass": counts[Verdict.PASS],
        "warn": counts[Verdict.WARN],
        "fail": counts[Verdict.FAIL],
        "actionable_fail": len(actionable),
        "is_ok": len(actionable) == 0,
        "actionable_is_ok": len(actionable) == 0,
        "spacy_ner_available": spacy_ner_available(),
        "masked_columns_checked": len(masked_checks),
        "leak_probes": len(DEMO_CORP_LEAK_PROBES),
        "failure_samples": failure_samples,
    }


async def _assert_single_pk_column_changed(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    qualified_table: str,
    column: str,
    *,
    limit: int = 10,
) -> None:
    schema, _, table = qualified_table.partition(".")
    rows = await source.fetch(
        f'SELECT id, "{column}" AS value FROM "{schema}"."{table}" '  # noqa: S608
        f'WHERE "{column}" IS NOT NULL LIMIT {int(limit)}'
    )
    assert rows, f"No sample rows for {qualified_table}.{column}"
    for row in rows:
        masked = await target.fetchval(
            f'SELECT "{column}" FROM "{schema}"."{table}" WHERE id = $1',  # noqa: S608
            row["id"],
        )
        assert masked is not None
        source_text = str(row["value"])
        expected = mask_entities_in_text(
            source_text,
            salt=TEST_SALT,
            column_path=f"{qualified_table}.{column}",
        )
        assert (
            masked == expected
        ), f"{qualified_table}.{column} mismatch for id={row['id']}"


async def _assert_composite_pk_column_changed(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    qualified_table: str,
    pk_columns: tuple[str, ...],
    column: str,
    *,
    limit: int = 10,
) -> None:
    schema, _, table = qualified_table.partition(".")
    pk_sql = ", ".join(f'"{name}"' for name in pk_columns)
    rows = await source.fetch(
        f'SELECT {pk_sql}, "{column}" AS value FROM "{schema}"."{table}" '  # noqa: S608
        f'WHERE "{column}" IS NOT NULL LIMIT {int(limit)}'
    )
    assert rows, f"No sample rows for {qualified_table}.{column}"
    for row in rows:
        where = " AND ".join(
            f'"{name}" = ${idx}' for idx, name in enumerate(pk_columns, 1)
        )
        params = [row[name] for name in pk_columns]
        physical_table = await source.fetchval(
            f'SELECT tableoid::regclass::text FROM "{schema}"."{table}" WHERE {where}',  # noqa: S608
            *params,
        )
        assert physical_table is not None
        physical_table = str(physical_table).strip('"')
        masked = await target.fetchval(
            f'SELECT "{column}" FROM "{schema}"."{table}" WHERE {where}',  # noqa: S608
            *params,
        )
        assert masked is not None
        pk_label = ", ".join(f"{name}={row[name]!r}" for name in pk_columns)
        source_text = str(row["value"])
        expected = mask_entities_in_text(
            source_text,
            salt=TEST_SALT,
            column_path=f"{physical_table}.{column}",
        )
        assert masked == expected, f"{physical_table}.{column} mismatch for {pk_label}"


async def assert_json_payload_masked(
    conn: asyncpg.Connection,
    *,
    table: str,
    column: str,
    row_id: int,
    forbidden_email: str,
    forbidden_token: str,
) -> None:
    """Assert JSON path masking on one row."""
    schema, _, name = table.partition(".")
    payload = await conn.fetchval(
        f'SELECT "{column}" FROM "{schema}"."{name}" WHERE id = $1',  # noqa: S608
        row_id,
    )
    assert payload is not None
    assert payload["contact"]["email"] != forbidden_email
    assert payload["contact"]["name"] == "Alice"
    assert payload["token"] != forbidden_token
    assert "debug" not in payload
    assert payload["note"] is None
