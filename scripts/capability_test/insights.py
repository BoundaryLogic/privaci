"""Post-run metrics and checks per capability kind."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from scripts.capability_test.registry import Capability

# Demo Corp mini-tier tables (full-run baseline).
_DEMO_CORP_TABLES: tuple[str, ...] = (
    "public.organizations",
    "public.users",
    "public.subscriptions",
    "public.invoices",
    "public.employees",
    "public.tickets",
    "clinical.providers",
    "clinical.patients",
    "auth.sessions",
)

# Acyclic subsetting-demo fixture (integration test for commercial-subsetting).
_SUBSETTING_DEMO_TABLES: tuple[str, ...] = (
    "public.organizations",
    "public.users",
    "public.orders",
)

_SUBSETTING_DEMO_FK_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "users.org_id → organizations.id",
        """
        SELECT count(*)::int FROM public.users u
        WHERE NOT EXISTS (
            SELECT 1 FROM public.organizations o WHERE o.id = u.org_id
        )
        """,
    ),
    (
        "orders.user_id → users.id",
        """
        SELECT count(*)::int FROM public.orders o
        WHERE NOT EXISTS (
            SELECT 1 FROM public.users u WHERE u.id = o.user_id
        )
        """,
    ),
)

_DEMO_CORP_FK_CHECKS: tuple[tuple[str, str], ...] = (
    (
        "users.org_id → organizations.id",
        """
        SELECT count(*)::int FROM public.users u
        WHERE NOT EXISTS (
            SELECT 1 FROM public.organizations o WHERE o.id = u.org_id
        )
        """,
    ),
    (
        "organizations.owner_user_id → users.id",
        """
        SELECT count(*)::int FROM public.organizations o
        WHERE o.owner_user_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM public.users u WHERE u.id = o.owner_user_id
          )
        """,
    ),
    (
        "organizations.primary_user_id → users.id",
        """
        SELECT count(*)::int FROM public.organizations o
        WHERE o.primary_user_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM public.users u WHERE u.id = o.primary_user_id
          )
        """,
    ),
    (
        "subscriptions.org_id → organizations.id",
        """
        SELECT count(*)::int FROM public.subscriptions s
        WHERE NOT EXISTS (
            SELECT 1 FROM public.organizations o WHERE o.id = s.org_id
        )
        """,
    ),
    (
        "tickets.org_id → organizations.id",
        """
        SELECT count(*)::int FROM public.tickets t
        WHERE NOT EXISTS (
            SELECT 1 FROM public.organizations o WHERE o.id = t.org_id
        )
        """,
    ),
)


@dataclass(frozen=True, slots=True)
class _SubsettingProfile:
    """Tables, FK checks, and narrative context for subsetting metrics."""

    name: str
    fixture_label: str
    root_predicate: str
    tables: tuple[str, ...]
    fk_checks: tuple[tuple[str, str], ...]
    expected_slice: dict[str, int] | None = None
    full_corpus: dict[str, int] | None = None


_PROFILES: dict[str, _SubsettingProfile] = {
    "subsetting-demo": _SubsettingProfile(
        name="subsetting-demo",
        fixture_label="Acyclic tenant graph (3 orgs, 10 users, 23 orders)",
        root_predicate="public.organizations id = 1",
        tables=_SUBSETTING_DEMO_TABLES,
        fk_checks=_SUBSETTING_DEMO_FK_CHECKS,
        expected_slice={"organizations": 1, "users": 2, "orders": 4},
        full_corpus={"organizations": 3, "users": 10, "orders": 23},
    ),
    "demo-corp": _SubsettingProfile(
        name="demo-corp",
        fixture_label="Demo Corp mini-tier (cross-org primary_user_id chain)",
        root_predicate="public.organizations id = 1",
        tables=_DEMO_CORP_TABLES,
        fk_checks=_DEMO_CORP_FK_CHECKS,
        full_corpus={"organizations": 20, "users": 200},
    ),
}


@dataclass(frozen=True, slots=True)
class CapabilityMetrics:
    """Structured metrics attached to a capability report row."""

    kind: str
    summary: str
    data: dict[str, Any]


def collect_capability_metrics(
    cap: Capability,
    *,
    source_dsn: str,
    target_dsn: str,
    pytest_exit_code: int | None,
    pytest_output: str,
) -> CapabilityMetrics | None:
    """Collect metrics for one capability run (best-effort)."""
    pytest_block = _parse_pytest_summary(pytest_output)
    base: dict[str, Any] = {
        "pytest": pytest_block,
        "scope": cap.metrics_scope,
        "scope_label": _scope_label(cap.metrics_scope),
    }

    if cap.metrics_scope == "infra":
        return _infra_metrics(cap, base, pytest_block, pytest_exit_code)

    if cap.metrics_scope == "autodetect" and pytest_exit_code == 0:
        return _autodetect_metrics(base, target_dsn, pytest_block)

    if cap.metrics_scope == "json-mask" and pytest_exit_code == 0:
        return _json_mask_metrics(base, target_dsn, pytest_block)

    if cap.metrics_kind == "subsetting" and pytest_exit_code == 0:
        profile = _resolve_subsetting_profile(source_dsn)
        postgres_block = _postgres_retention(
            source_dsn,
            target_dsn,
            tables=profile.tables,
            fixture_label=profile.fixture_label,
        )
        fk_block = _run_fk_checks(target_dsn, profile.fk_checks)
        closure_block = _subsetting_closure_summary(source_dsn, profile)
        assessment = _subsetting_assessment(profile, postgres_block, closure_block)
        data = {
            **base,
            **postgres_block,
            "fk_checks": fk_block,
            **closure_block,
            "assessment": assessment,
            "profile": profile.name,
        }
        summary = assessment.get("headline") or _retention_summary(postgres_block)
        return CapabilityMetrics(kind="subsetting", summary=summary, data=data)

    if cap.metrics_scope == "demo-corp" and pytest_exit_code == 0:
        return _demo_corp_masking_metrics(
            base,
            source_dsn=source_dsn,
            target_dsn=target_dsn,
            pytest_block=pytest_block,
        )

    if cap.metrics_kind == "unit" or pytest_block:
        passed = pytest_block.get("passed", 0)
        failed = pytest_block.get("failed", 0)
        summary = f"pytest: {passed} passed"
        if failed:
            summary = f"pytest: {passed} passed, {failed} failed"
        return CapabilityMetrics(kind="unit", summary=summary, data=base)

    return None


def _scope_label(scope: str) -> str:
    labels = {
        "none": "Unit test",
        "infra": "Pipeline infrastructure (not a masking audit)",
        "demo-corp": "Demo Corp full masking audit",
        "autodetect": "Auto-detect + mask on Postgres",
        "json-mask": "Commercial JSONB path masking",
        "subsetting": "FK-aware subsetting slice",
        "nlp": "SpaCy L2 NER stack (required for demo-corp)",
    }
    return labels.get(scope, scope)


def _infra_metrics(
    cap: Capability,
    base: dict[str, Any],
    pytest_block: dict[str, Any],
    pytest_exit_code: int | None,
) -> CapabilityMetrics:
    passed = pytest_block.get("passed", 0)
    failed = pytest_block.get("failed", 0)
    note = (
        f"{cap.label} exercises isolated SQL fixtures (resume, spikes, preview). "
        "Demo Corp retention tables below do not apply — see masking-capable "
        "capabilities in the suite summary."
    )
    summary = f"pytest: {passed} passed — infrastructure scope (masking N/A)"
    if failed:
        summary = f"pytest: {passed} passed, {failed} failed"
    elif pytest_exit_code != 0:
        summary = f"pytest failed (exit {pytest_exit_code})"
    return CapabilityMetrics(
        kind="infra",
        summary=summary,
        data={**base, "infra_note": note, "masking_applicable": False},
    )


def _demo_corp_masking_metrics(
    base: dict[str, Any],
    *,
    source_dsn: str,
    target_dsn: str,
    pytest_block: dict[str, Any],
) -> CapabilityMetrics:
    import asyncio

    has_demo_target = asyncio.run(_table_exists(target_dsn, "public", "users"))
    if not has_demo_target:
        note = (
            "Demo Corp not present on target after this run — "
            "masking metrics skipped (likely superseded by a later capability)."
        )
        return CapabilityMetrics(
            kind="masking_quality",
            summary=note,
            data={
                **base,
                "masking_applicable": False,
                "masking": {"available": False, "detail": note},
            },
        )

    postgres_block = _postgres_retention(
        source_dsn,
        target_dsn,
        tables=_DEMO_CORP_TABLES,
        fixture_label="Demo Corp core tables",
    )
    fk_block = _run_fk_checks(target_dsn, _DEMO_CORP_FK_CHECKS)
    masking_block = _masking_quality_metrics(source_dsn, target_dsn)
    data = {
        **base,
        **postgres_block,
        "fk_checks": fk_block,
        **masking_block,
        "masking_applicable": True,
    }
    summary = masking_block.get("headline", _retention_summary(postgres_block))
    return CapabilityMetrics(kind="masking_quality", summary=summary, data=data)


def _autodetect_metrics(
    base: dict[str, Any],
    target_dsn: str,
    pytest_block: dict[str, Any],
) -> CapabilityMetrics:
    import asyncio

    block = asyncio.run(_autodetect_metrics_async(target_dsn))
    passed = pytest_block.get("passed", 0)
    summary = (
        f"Auto-detect: {block.get('detection', 'n/a')} · "
        f"masking: {block.get('masking', 'n/a')} · pytest: {passed} passed"
    )
    return CapabilityMetrics(
        kind="masking_quality",
        summary=summary,
        data={**base, **block, "masking_applicable": True},
    )


async def _autodetect_metrics_async(target_dsn: str) -> dict[str, Any]:
    import asyncpg

    forbidden = ("alice@example.test", "bob@example.test")
    conn = await asyncpg.connect(target_dsn)
    try:
        if not await _table_exists_on_conn(conn, "autodetect_demo", "contacts"):
            return {
                "masking": {
                    "available": False,
                    "detail": "autodetect_demo not on target",
                },
            }
        leaked = 0
        for email in forbidden:
            found = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM autodetect_demo.contacts WHERE email = $1
                )
                """,
                email,
            )
            if found:
                leaked += 1
        statuses = await conn.fetchval(
            "SELECT count(DISTINCT status)::int FROM autodetect_demo.contacts"
        )
    finally:
        await conn.close()

    return {
        "detection": "email → fake/email (asserted in pytest)",
        "masking": "pass" if leaked == 0 else f"FAIL ({leaked} seed email(s) leaked)",
        "autodetect": {
            "seed_emails_leaked": leaked,
            "passthrough_status_values": int(statuses or 0),
        },
    }


def _json_mask_metrics(
    base: dict[str, Any],
    target_dsn: str,
    pytest_block: dict[str, Any],
) -> CapabilityMetrics:
    import asyncio

    block = asyncio.run(_json_mask_metrics_async(target_dsn))
    passed = pytest_block.get("passed", 0)
    summary = f"JSONB paths: {block.get('masking', 'n/a')} · pytest: {passed} passed"
    return CapabilityMetrics(
        kind="masking_quality",
        summary=summary,
        data={**base, **block, "masking_applicable": True},
    )


async def _json_mask_metrics_async(target_dsn: str) -> dict[str, Any]:
    import json

    import asyncpg

    conn = await asyncpg.connect(target_dsn)
    try:
        if not await _table_exists_on_conn(conn, "public", "event_log"):
            return {
                "masking": {
                    "available": False,
                    "detail": "event_log not on target",
                },
            }
        raw = await conn.fetchval("SELECT payload FROM public.event_log WHERE id = 1")
    finally:
        await conn.close()

    if raw is None:
        return {"masking": "FAIL — no rows on target"}
    payload = json.loads(raw) if isinstance(raw, str) else raw
    seed_token = "secret-tok"  # noqa: S105 — fixture probe, not a credential
    checks = {
        "email_faked": payload["contact"]["email"] != "alice@acme.example",
        "token_hashed": payload["token"] != seed_token,
        "debug_removed": "debug" not in payload,
        "note_nulled": payload.get("note") is None,
        "name_passthrough": payload["contact"]["name"] == "Alice",
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "masking": "pass" if not failed else f"FAIL ({', '.join(failed)})",
        "json_mask_checks": checks,
    }


async def _table_exists_on_conn(
    conn: Any,
    schema: str,
    table: str,
) -> bool:
    found = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = $1 AND table_name = $2 LIMIT 1
        """,
        schema,
        table,
    )
    return found is not None


def aggregate_masking_confidence(
    capability_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build suite-level masking confidence from capability metrics."""
    audited: list[dict[str, Any]] = []
    infra: list[str] = []
    for row in capability_rows:
        metrics = row.get("metrics") or {}
        data = metrics.get("data") or {}
        scope = data.get("scope", "none")
        if scope == "infra":
            infra.append(row["id"])
            continue
        if not data.get("masking_applicable") and scope != "subsetting":
            masking_raw = data.get("masking")
            masking_unavail = (
                isinstance(masking_raw, dict) and masking_raw.get("available") is False
            )
            if masking_unavail and scope == "demo-corp":
                continue
            if scope in {"none"}:
                continue
        entry: dict[str, Any] = {
            "id": row["id"],
            "label": row["label"],
            "scope": scope,
            "summary": metrics.get("summary", ""),
        }
        masking = data.get("masking")
        if masking:
            entry["masking"] = masking
        if data.get("assessment"):
            entry["assessment"] = data["assessment"]
        if data.get("autodetect"):
            entry["autodetect"] = data["autodetect"]
        if data.get("json_mask_checks"):
            entry["json_mask_checks"] = data["json_mask_checks"]
        audited.append(entry)

    return {
        "audited_capabilities": audited,
        "infrastructure_only": infra,
        "audited_count": len(audited),
    }


def masking_metrics_status(
    cap: Capability,
    metrics: CapabilityMetrics | None,
) -> str | None:
    """Return post-metrics status override: failed, warn, or None (keep pytest status)."""
    issues = masking_metrics_issues(cap, metrics)
    if any(issue.startswith("FAIL:") for issue in issues):
        return "failed"
    if any(issue.startswith("WARN:") for issue in issues):
        return "warn"
    return None


def masking_metrics_issues(
    cap: Capability,
    metrics: CapabilityMetrics | None,
) -> list[str]:
    """Human-readable masking findings from post-run metrics."""
    if metrics is None:
        return []
    data = metrics.data
    issues: list[str] = []

    if cap.metrics_scope == "demo-corp" and data.get("spacy_ner_available") is False:
        detail = (data.get("masking") or {}).get("detail", "SpaCy NER unavailable")
        issues.append(f"FAIL: {detail}")

    masking = data.get("masking")
    if isinstance(masking, dict):
        probes = masking.get("leak_probes") or {}
        run_count = int(probes.get("probes_run", 0))
        passed_count = int(probes.get("probes_passed", 0))
        if run_count and passed_count < run_count:
            issues.append(f"FAIL: leak probes {passed_count}/{run_count} passed")
        verify = masking.get("verify") or {}
        if (
            verify.get("actionable_fail", 0) > 0
            or verify.get("actionable_is_ok") is False
        ):
            samples = verify.get("failure_samples") or []
            if samples:
                detail = "; ".join(
                    f"{s.get('target', '?')}: {s.get('detail', '')}"
                    for s in samples[:3]
                )
                issues.append(f"FAIL: verify — {detail}")
            elif verify.get("detail"):
                issues.append(f"FAIL: verify — {verify['detail']}")
            else:
                issues.append(
                    f"FAIL: verify — {verify.get('actionable_fail', '?')} "
                    "actionable failure(s)"
                )

    elif isinstance(masking, str) and masking.upper().startswith("FAIL"):
        issues.append(f"FAIL: masking — {masking}")

    if cap.metrics_scope == "json-mask":
        checks = data.get("json_mask_checks") or {}
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            issues.append(f"FAIL: JSONB checks — {', '.join(failed)}")

    autodetect = data.get("autodetect") or {}
    if autodetect.get("seed_emails_leaked", 0) > 0:
        issues.append(
            f"FAIL: autodetect — {autodetect['seed_emails_leaked']} seed email(s) leaked"
        )

    return issues


def summarize_masking_findings(
    capability_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Suite-level actionable vs informational masking findings."""
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for row in capability_rows:
        cap_id = row["id"]
        for issue in row.get("issues") or []:
            if issue.startswith("FAIL:"):
                failures.append({"id": cap_id, "detail": issue[5:].strip()})
            elif issue.startswith("WARN:"):
                warnings.append({"id": cap_id, "detail": issue[5:].strip()})
    return {
        "actionable_failures": failures,
        "informational_warnings": warnings,
        "has_actionable_failures": bool(failures),
        "has_warnings": bool(warnings),
    }


def _masking_quality_metrics(source_dsn: str, target_dsn: str) -> dict[str, Any]:
    """Post-run masking quality signals when demo-corp data is on the target."""
    import asyncio

    return asyncio.run(_masking_quality_metrics_async(source_dsn, target_dsn))


async def _masking_quality_metrics_async(
    source_dsn: str,
    target_dsn: str,
) -> dict[str, Any]:
    import asyncpg

    from privaci.config import load_config
    from privaci.verify.runner import run_verification
    from scripts.capability_test.compose_dev import engine_root
    from tests.integration.masking_checks import (
        DEMO_CORP_LEAK_PROBES,
        assert_demo_corp_leak_probes,
        run_demo_corp_verification,
        verification_summary,
    )
    from tests.integration.spacy_requirements import (
        spacy_ner_available,
        spacy_ner_blocker,
    )

    if not spacy_ner_available():
        reason = spacy_ner_blocker() or "SpaCy NER unavailable"
        return {
            "headline": f"Masking quality: FAIL — {reason}",
            "spacy_ner_available": False,
            "masking": {
                "available": False,
                "detail": reason,
            },
        }

    if not await _table_exists(target_dsn, "public", "users"):
        return {
            "masking": {
                "available": False,
                "detail": "No demo-corp target data to assess",
            }
        }

    config_path = engine_root() / "tests" / "fixtures" / "configs" / "demo-corp.yaml"
    config = load_config(config_path)
    leak_stats: dict[str, int] = {
        "probes_run": len(DEMO_CORP_LEAK_PROBES),
        "probes_passed": 0,
    }
    verify_summary: dict[str, Any] | None = None

    conn = await asyncpg.connect(target_dsn)
    try:
        leak_stats = await assert_demo_corp_leak_probes(conn)
    except AssertionError:
        leak_stats = {
            "probes_run": len(DEMO_CORP_LEAK_PROBES),
            "probes_passed": 0,
        }
    finally:
        await conn.close()

    try:
        report = await run_demo_corp_verification(
            config=config,
            source_dsn=source_dsn,
            target_dsn=target_dsn,
        )
        verify_summary = verification_summary(report)
    except AssertionError as exc:
        report = await run_verification(
            config=config,
            source_dsn=source_dsn,
            target_dsn=target_dsn,
            sample_size=500,
        )
        verify_summary = verification_summary(report)
        verify_summary["detail"] = str(exc)[:500]
    except (OSError, ValueError, RuntimeError) as exc:
        verify_summary = {
            "is_ok": False,
            "actionable_is_ok": False,
            "actionable_fail": 1,
            "fail": 1,
            "detail": str(exc)[:500],
            "failure_samples": [],
        }

    verify_ok = (
        verify_summary.get("actionable_is_ok", verify_summary.get("is_ok"))
        if verify_summary
        else True
    )
    headline = (
        f"Masking quality: {leak_stats['probes_passed']}/{leak_stats['probes_run']} "
        f"leak probes, verify {'OK' if verify_ok else 'FAIL'}"
    )
    return {
        "headline": headline,
        "spacy_ner_available": True,
        "masking_applicable": True,
        "masking": {
            "available": True,
            "leak_probes": leak_stats,
            "configured_probes": len(DEMO_CORP_LEAK_PROBES),
            "verify": verify_summary,
        },
    }


def _resolve_subsetting_profile(source_dsn: str) -> _SubsettingProfile:
    env_key = os.environ.get("CAPABILITY_SUBSETTING_PROFILE", "").strip()
    if env_key in _PROFILES:
        return _PROFILES[env_key]
    import asyncio

    has_orders = asyncio.run(_table_exists(source_dsn, "public", "orders"))
    has_clinical = asyncio.run(_table_exists(source_dsn, "clinical", "patients"))
    if has_orders and not has_clinical:
        return _PROFILES["subsetting-demo"]
    return _PROFILES["demo-corp"]


async def _table_exists(dsn: str, schema: str, table: str) -> bool:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        found = await conn.fetchval(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = $2
            LIMIT 1
            """,
            schema,
            table,
        )
        return found is not None
    finally:
        await conn.close()


def _retention_summary(data: dict[str, Any]) -> str:
    totals = data.get("totals", {})
    source = int(totals.get("source_rows", 0))
    target = int(totals.get("target_rows", 0))
    pct = totals.get("retention_pct")
    label = data.get("fixture_label", "tracked tables")
    if source > 0 and target == 0:
        return (
            f"No {label} rows on target after run "
            f"(source baseline: {source:,}) — isolated-schema test or metrics timing"
        )
    if pct is None:
        return f"Target rows: {target} (source baseline: {source})"
    return f"Retained {pct}% of {label} ({target:,}/{source:,} rows)"


def _subsetting_assessment(
    profile: _SubsettingProfile,
    postgres_block: dict[str, Any],
    closure_block: dict[str, Any],
) -> dict[str, Any]:
    totals = postgres_block.get("totals", {})
    retention_pct = totals.get("retention_pct")
    source_rows = int(totals.get("source_rows", 0))
    target_rows = int(totals.get("target_rows", 0))
    closure = closure_block.get("closure", {})

    slice_effective = (
        retention_pct is not None
        and float(retention_pct) < 90.0
        and target_rows < source_rows
    )

    rows_by_table = closure.get("rows_by_table", {})
    orgs_in_closure = rows_by_table.get("public.organizations", 0)
    users_in_closure = rows_by_table.get("public.users", 0)
    orders_in_closure = rows_by_table.get("public.orders", 0)

    expected = profile.expected_slice or {}
    full = profile.full_corpus or {}

    if profile.name == "subsetting-demo":
        headline = (
            f"Slice retained {retention_pct}% of fixture rows "
            f"({target_rows}/{source_rows}) — one tenant pulled via FK closure"
        )
        verdict = (
            f"Root `{profile.root_predicate}` copied org 1 only: "
            f"{orgs_in_closure} org, {users_in_closure} users, {orders_in_closure} orders "
            f"(full fixture: {full.get('organizations')} orgs, "
            f"{full.get('users')} users, {full.get('orders')} orders)."
        )
        operator_note = (
            "Use this fixture to validate that subsetting shrinks copy volume. "
            "Compare retention % to your production root predicate before go-live."
        )
    elif slice_effective:
        headline = _retention_summary(postgres_block)
        verdict = "FK closure reduced row volume versus the tracked source baseline."
        operator_note = "Review per-table retention for tables outside the tracked set."
    else:
        headline = (
            "Subsetting ran but did not shrink tracked rows "
            f"({retention_pct}% retained)"
        )
        verdict = (
            f"Root `{profile.root_predicate}` expanded via FK closure to "
            f"{orgs_in_closure} org(s) and {users_in_closure} user(s) on demo-corp. "
            "Cross-org links (e.g. organizations.primary_user_id) can pull the "
            "entire tenant graph — retention near 100% does not mean closure is broken."
        )
        operator_note = (
            "For a meaningful shrink test, use an acyclic fixture or a root table "
            "whose FK graph stays inside one tenant. Re-run with subsetting-demo "
            "integration tests or a production predicate that isolates one tenant."
        )

    return {
        "slice_effective": slice_effective,
        "headline": headline,
        "verdict": verdict,
        "operator_note": operator_note,
        "root_predicate": profile.root_predicate,
        "fixture": profile.fixture_label,
        "expected_slice": expected,
        "full_corpus": full,
        "closure_orgs": orgs_in_closure,
        "closure_users": users_in_closure,
        "closure_orders": orders_in_closure,
    }


def _parse_pytest_summary(output: str) -> dict[str, Any]:
    text = output.strip()
    block: dict[str, Any] = {"tests": [], "passed": 0, "failed": 0, "skipped": 0}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("tests/") or stripped.startswith("FAILED "):
            block["tests"].append(stripped)
    summary_line = ""
    for line in reversed(text.splitlines()):
        if " passed" in line or " failed" in line or " error" in line:
            summary_line = line.strip()
            break
    block["summary_line"] = summary_line
    for key in ("passed", "failed", "skipped", "error"):
        match = re.search(rf"(\d+) {key}", summary_line)
        if match:
            block[key] = int(match.group(1))
    return block


def _postgres_retention(
    source_dsn: str,
    target_dsn: str,
    *,
    tables: tuple[str, ...],
    fixture_label: str,
) -> dict[str, Any]:
    import asyncio

    block = asyncio.run(
        _postgres_retention_async(source_dsn, target_dsn, tables=tables)
    )
    block["fixture_label"] = fixture_label
    return block


async def _postgres_retention_async(
    source_dsn: str,
    target_dsn: str,
    *,
    tables: tuple[str, ...],
) -> dict[str, Any]:
    per_table: dict[str, dict[str, int | float | None]] = {}
    source_total = 0
    target_total = 0

    for qualified in tables:
        schema, _, table = qualified.partition(".")
        source_count = await _safe_count(source_dsn, schema, table)
        target_count = await _safe_count(target_dsn, schema, table)
        if source_count is None and target_count is None:
            continue
        src = source_count or 0
        tgt = target_count or 0
        source_total += src
        target_total += tgt
        pct: float | None = round(100.0 * tgt / src, 2) if src else None
        per_table[qualified] = {
            "source_rows": src,
            "target_rows": tgt,
            "retention_pct": pct,
        }

    total_pct: float | None = (
        round(100.0 * target_total / source_total, 2) if source_total else None
    )
    return {
        "tables": per_table,
        "totals": {
            "source_rows": source_total,
            "target_rows": target_total,
            "retention_pct": total_pct,
        },
    }


async def _safe_count(dsn: str, schema: str, table: str) -> int | None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        return int(
            await conn.fetchval(
                f'SELECT count(*)::int FROM "{schema}"."{table}"'  # noqa: S608
            )
            or 0
        )
    except asyncpg.UndefinedTableError:
        return None
    finally:
        await conn.close()


def _run_fk_checks(
    target_dsn: str,
    checks: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    import asyncio

    return asyncio.run(_run_fk_checks_async(target_dsn, checks))


async def _run_fk_checks_async(
    target_dsn: str,
    checks: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    import asyncpg

    results: list[dict[str, Any]] = []
    conn = await asyncpg.connect(target_dsn)
    try:
        for name, query in checks:
            try:
                violations = int(await conn.fetchval(query) or 0)
            except asyncpg.UndefinedTableError:
                results.append(
                    {
                        "name": name,
                        "passed": True,
                        "violations": None,
                        "detail": "table not on target (skipped)",
                        "skipped": True,
                    }
                )
                continue
            passed = violations == 0
            detail = "ok" if passed else f"{violations} orphan row(s)"
            results.append(
                {
                    "name": name,
                    "passed": passed,
                    "violations": violations,
                    "detail": detail,
                }
            )
    finally:
        await conn.close()
    return results


def _subsetting_closure_summary(
    source_dsn: str, profile: _SubsettingProfile
) -> dict[str, Any]:
    """Best-effort FK-closure stats when commercial is installed."""
    try:
        import asyncio

        return asyncio.run(_subsetting_closure_async(source_dsn, profile))
    except (ImportError, ModuleNotFoundError, OSError, ValueError):
        return {"closure": {"available": False}}


async def _subsetting_closure_async(
    source_dsn: str,
    profile: _SubsettingProfile,
) -> dict[str, Any]:
    import asyncpg
    from privaci_commercial.config.commercial_extensions import RootSubsetFilter
    from privaci_commercial.subsetting.closure import compute_subset_pk_closure

    from privaci.catalog.introspect import introspect_catalog

    table_part, _, predicate = profile.root_predicate.partition(" id = ")
    roots = [
        RootSubsetFilter(
            table=table_part.strip(), predicate=f"id = {predicate.strip()}"
        )
    ]

    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
        pk_sets = await compute_subset_pk_closure(conn, catalog, roots)
    finally:
        await conn.close()

    table_rows = {tid: len(pks) for tid, pks in pk_sets.items()}
    return {
        "closure": {
            "available": True,
            "root_predicate": profile.root_predicate,
            "tables_in_closure": len(table_rows),
            "rows_by_table": table_rows,
            "organizations": table_rows.get("public.organizations", 0),
            "users": table_rows.get("public.users", 0),
            "orders": table_rows.get("public.orders", 0),
        }
    }
