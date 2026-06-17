"""Write JSON and Markdown capability test reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.capability_test.insights import (
    CapabilityMetrics,
    aggregate_masking_confidence,
    summarize_masking_findings,
)
from scripts.capability_test.runner import CapabilityResult


def _masking_detail(masking: Any) -> dict[str, Any] | None:
    """Return masking block when metrics store a dict (demo-corp verify/leak probes)."""
    return masking if isinstance(masking, dict) else None


def _masking_result(masking: Any) -> str | None:
    """Return short masking verdict when metrics store a string (autodetect, json-mask)."""
    return masking if isinstance(masking, str) else None


def _validation_dict(result: CapabilityResult) -> list[dict[str, Any]]:
    return [
        {
            "name": v.name,
            "passed": v.passed,
            "detail": v.detail,
            "data": v.data,
        }
        for v in result.validations
    ]


def _metrics_dict(metrics: CapabilityMetrics | None) -> dict[str, Any] | None:
    if metrics is None:
        return None
    return {
        "kind": metrics.kind,
        "summary": metrics.summary,
        "data": metrics.data,
    }


def build_report_payload(
    *,
    results: list[CapabilityResult],
    prep_logs: list[str],
    selected: list[str],
    environment: dict[str, Any],
    suite: str | None = None,
    suite_phases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the full report document."""
    finished = datetime.now(tz=UTC)
    summary = {"passed": 0, "failed": 0, "warn": 0, "error": 0}
    capability_rows: list[dict[str, Any]] = []

    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
        capability_rows.append(
            {
                "id": result.capability_id,
                "label": result.label,
                "repo": result.repo,
                "status": result.status,
                "duration_sec": result.duration_sec,
                "pytest_exit_code": result.pytest_exit_code,
                "validations": _validation_dict(result),
                "metrics": _metrics_dict(result.metrics),
                "issues": list(result.issues),
                "pytest_output_tail": _tail(result.pytest_output, max_lines=40),
            }
        )

    payload: dict[str, Any] = {
        "report_version": "2",
        "generated_at": finished.isoformat(),
        "selected_capabilities": selected,
        "environment": environment,
        "prep": {"steps": prep_logs},
        "summary": summary,
        "capabilities": capability_rows,
    }
    if suite:
        payload["suite"] = suite
    if suite_phases:
        payload["suite_phases"] = suite_phases
    payload["masking_confidence"] = aggregate_masking_confidence(capability_rows)
    payload["masking_findings"] = summarize_masking_findings(capability_rows)
    return payload


def _tail(text: str, *, max_lines: int) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    omitted = len(lines) - max_lines
    return "\n".join([f"... ({omitted} lines omitted) ...", *lines[-max_lines:]])


def write_reports(
    payload: dict[str, Any],
    output_dir: Path,
    *,
    stem: str = "capability-report",
) -> tuple[Path, Path]:
    """Write ``.json`` and ``.md`` reports; return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"{stem}-{stamp}.json"
    md_path = output_dir / f"{stem}-{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PrivaCI capability test report",
        "",
        f"Generated: {payload['generated_at']}",
    ]
    if payload.get("suite"):
        lines.append(f"Suite: **{payload['suite']}**")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Result | Count |",
            "|--------|------:|",
            f"| Passed | {summary.get('passed', 0)} |",
            f"| Failed | {summary.get('failed', 0)} |",
            f"| Warn   | {summary.get('warn', 0)} |",
            f"| Error  | {summary.get('error', 0)} |",
            "",
        ]
    )

    findings = payload.get("masking_findings") or {}
    failures = findings.get("actionable_failures") or []
    warnings = findings.get("informational_warnings") or []
    if failures or warnings:
        lines.extend(["## Masking findings", ""])
        if failures:
            lines.append(
                f"**{len(failures)} actionable masking failure(s)** "
                "(capability marked FAIL):"
            )
            lines.append("")
            for item in failures:
                lines.append(f"- `{item['id']}`: {item['detail']}")
            lines.append("")
        if warnings:
            lines.append(
                f"**{len(warnings)} incomplete-audit warning(s)** "
                "(capability marked WARN — pytest passed but masking audit "
                "was not fully exercised):"
            )
            lines.append("")
            for item in warnings:
                lines.append(f"- `{item['id']}`: {item['detail']}")
            lines.append("")

    lines.extend(["## Environment", ""])
    for key, value in payload.get("environment", {}).items():
        if "password" in key.lower() or "salt" in key.lower() or "key" in key.lower():
            value = "<redacted>"
        lines.append(f"- `{key}`: {value}")

    if payload.get("suite_phases"):
        lines.extend(["", "## Suite phases", ""])
        for phase in payload["suite_phases"]:
            lines.append(
                f"- Phase {phase['index']}: {', '.join(phase['groups'])} "
                f"({phase.get('capability_count', 0)} capabilities)"
            )

    lines.extend(["", "## Prep", ""])
    for step in payload.get("prep", {}).get("steps", []):
        lines.append(f"- {step}")

    masking_conf = payload.get("masking_confidence") or {}
    audited = masking_conf.get("audited_capabilities") or []
    infra_only = masking_conf.get("infrastructure_only") or []
    if audited or infra_only:
        lines.extend(["", "## Masking confidence", ""])
        lines.append(
            "Capabilities that **audit masking** vs those that only test "
            "pipeline infrastructure (resume, streaming, preview)."
        )
        lines.append("")
        if audited:
            lines.append(
                f"**{len(audited)} capability(ies) audited masking** "
                "(leak probes, verify, or fixture-specific checks):"
            )
            lines.append("")
            for entry in audited:
                scope = entry.get("scope", "?")
                lines.append(f"- `{entry['id']}` ({scope}): {entry.get('summary', '')}")
                masking = _masking_detail(entry.get("masking"))
                masking_result = _masking_result(entry.get("masking"))
                if masking_result and not masking:
                    lines.append(f"  - Masking: **{masking_result}**")
                if masking and masking.get("leak_probes"):
                    probes = masking["leak_probes"]
                    lines.append(
                        f"  - Leak probes: {probes.get('probes_passed', 0)}/"
                        f"{probes.get('probes_run', 0)}"
                    )
                verify = masking.get("verify") if masking else None
                if verify:
                    actionable_ok = verify.get("actionable_is_ok", verify.get("is_ok"))
                    status = "OK" if actionable_ok else "FAIL"
                    lines.append(
                        f"  - Verify: {status} "
                        f"(pass={verify.get('pass', 0)}, "
                        f"warn={verify.get('warn', 0)}, "
                        f"fail={verify.get('fail', 0)}, "
                        f"actionable_fail={verify.get('actionable_fail', 0)})"
                    )
                    for sample in verify.get("failure_samples") or []:
                        lines.append(
                            f"    - FAIL `{sample.get('target', '?')}`: "
                            f"{sample.get('detail', '')}"
                        )
                if entry.get("autodetect"):
                    ad = entry["autodetect"]
                    leaked = ad.get("seed_emails_leaked", 0)
                    lines.append(f"  - Seed emails leaked: {leaked}")
                if entry.get("json_mask_checks"):
                    failed = [
                        name for name, ok in entry["json_mask_checks"].items() if not ok
                    ]
                    if failed:
                        lines.append(f"  - JSONB checks failed: {', '.join(failed)}")
                    else:
                        lines.append("  - JSONB path checks: all passed")
                assessment = entry.get("assessment")
                if assessment and assessment.get("verdict"):
                    lines.append(f"  - Subsetting: {assessment['verdict']}")
            lines.append("")
        if infra_only:
            lines.append(
                "**Infrastructure-only** (pytest pass ≠ masking verified): "
                + ", ".join(f"`{cap_id}`" for cap_id in infra_only)
            )
            lines.append("")

    lines.extend(["", "## Capabilities", ""])
    for cap in payload.get("capabilities", []):
        icon = {"passed": "OK", "failed": "FAIL", "warn": "WARN", "error": "ERR"}.get(
            cap["status"], cap["status"]
        )
        lines.append(f"### {icon} — {cap['label']} (`{cap['id']}`)")
        lines.append("")
        lines.append(
            f"- Repo: `{cap['repo']}` · Duration: {cap['duration_sec']}s · "
            f"Status: **{cap['status']}**"
        )
        metrics = cap.get("metrics")
        if metrics:
            lines.append(f"- **Metrics:** {metrics.get('summary', '')}")
            _append_metrics_markdown(lines, metrics)
        if cap.get("issues"):
            lines.append("- **Issues:**")
            for issue in cap["issues"]:
                if issue.startswith("pytest exit"):
                    continue
                lines.append(f"  - {issue}")
        for val in cap.get("validations", []):
            mark = "pass" if val["passed"] else "FAIL"
            lines.append(f"- Validation `{val['name']}`: {mark} — {val['detail']}")
        if cap.get("pytest_output_tail"):
            lines.extend(["", "<details><summary>Pytest output</summary>", ""])
            lines.extend(["```text", cap["pytest_output_tail"], "```", ""])
            lines.append("</details>")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _append_metrics_markdown(lines: list[str], metrics: dict[str, Any]) -> None:
    data = metrics.get("data", {})
    kind = metrics.get("kind", "")
    scope = data.get("scope", "none")

    if data.get("scope_label"):
        lines.append(f"- Scope: **{data['scope_label']}**")

    if kind == "infra" or scope == "infra":
        note = data.get("infra_note")
        if note:
            lines.append(f"- **Note:** {note}")
        pytest_info = data.get("pytest", {})
        if pytest_info.get("summary_line"):
            lines.append(f"- Pytest: `{pytest_info['summary_line']}`")
        return

    pytest_info = data.get("pytest", {})
    if pytest_info.get("summary_line"):
        lines.append(f"- Pytest: `{pytest_info['summary_line']}`")

    masking_unavail_block = _masking_detail(data.get("masking"))
    if (
        data.get("masking_applicable") is False
        and masking_unavail_block
        and masking_unavail_block.get("detail")
    ):
        lines.append(f"- Masking metrics: {masking_unavail_block['detail']}")
        return

    if data.get("detection"):
        lines.append(f"- Auto-detect: {data['detection']}")
    masking_result = _masking_result(data.get("masking"))
    if masking_result:
        lines.append(f"- Masking result: **{masking_result}**")
    if data.get("json_mask_checks"):
        lines.append("")
        lines.append("| JSONB path check | Result |")
        lines.append("|------------------|--------|")
        for name, ok in sorted(data["json_mask_checks"].items()):
            lines.append(f"| `{name}` | {'pass' if ok else '**FAIL**'} |")

    totals = data.get("totals")
    if totals:
        pct = totals.get("retention_pct")
        src = totals.get("source_rows", 0)
        tgt = totals.get("target_rows", 0)
        label = data.get("fixture_label", "tracked tables")
        if pct is not None:
            lines.append(
                f"- Row retention ({label}): **{pct}%** " f"({tgt:,} / {src:,} rows)"
            )

    assessment = data.get("assessment")
    if assessment:
        effective = assessment.get("slice_effective")
        flag = "yes" if effective else "**no — read verdict**"
        lines.append(f"- Slice reduced data: {flag}")
        if assessment.get("verdict"):
            lines.append(f"- **Verdict:** {assessment['verdict']}")
        if assessment.get("operator_note"):
            lines.append(f"- **Note:** {assessment['operator_note']}")
        expected = assessment.get("expected_slice")
        full = assessment.get("full_corpus")
        if expected and full:
            lines.append(f"- Expected slice vs full fixture: " f"{expected} vs {full}")

    tables = data.get("tables")
    if tables:
        lines.append("")
        lines.append("| Table | Source | Target | Retained |")
        lines.append("|-------|-------:|-------:|---------:|")
        for name, row in sorted(tables.items()):
            pct = row.get("retention_pct")
            pct_text = f"{pct}%" if pct is not None else "—"
            lines.append(
                f"| `{name}` | {row.get('source_rows', 0):,} | "
                f"{row.get('target_rows', 0):,} | {pct_text} |"
            )

    closure = data.get("closure")
    if closure and closure.get("available"):
        lines.append("")
        orgs = closure.get("organizations", 0)
        users = closure.get("users", 0)
        orders = closure.get("orders")
        detail = f"{orgs} org(s), {users} user(s)"
        if orders is not None:
            detail = f"{detail}, {orders} order(s)"
        lines.append(
            f"- FK closure ({closure.get('root_predicate', 'n/a')}): "
            f"{closure.get('tables_in_closure', 0)} tables, {detail}"
        )

    fk_checks = data.get("fk_checks")
    if fk_checks:
        lines.append("")
        lines.append("**Referential checks (target):**")
        for check in fk_checks:
            if check.get("skipped"):
                lines.append(
                    f"- `{check.get('name', '?')}`: skipped — "
                    f"{check.get('detail', '')}"
                )
                continue
            mark = "pass" if check.get("passed") else "FAIL"
            lines.append(
                f"- `{check.get('name', '?')}`: {mark} — {check.get('detail', '')}"
            )

    masking = _masking_detail(data.get("masking"))
    if masking and masking.get("available"):
        probes = masking.get("leak_probes", {})
        lines.append("")
        lines.append(
            f"- **Masking leak probes:** {probes.get('probes_passed', 0)}/"
            f"{probes.get('probes_run', 0)} passed "
            f"(of {masking.get('configured_probes', '?')} configured)"
        )
        verify = masking.get("verify")
        if verify:
            actionable_ok = verify.get("actionable_is_ok", verify.get("is_ok"))
            verify_label = "OK" if actionable_ok else "FAIL"
            lines.append(
                f"- **Value-free verify:** {verify_label} — "
                f"pass={verify.get('pass', 0)}, "
                f"warn={verify.get('warn', 0)}, "
                f"fail={verify.get('fail', 0)}, "
                f"actionable_fail={verify.get('actionable_fail', 0)}, "
                f"masked columns sampled={verify.get('masked_columns_checked', 0)}"
            )
            for sample in verify.get("failure_samples") or []:
                lines.append(
                    f"  - FAIL `{sample.get('target', '?')}` "
                    f"({sample.get('check', '?')}): {sample.get('detail', '')}"
                )
            if verify.get("detail") and not verify.get("failure_samples"):
                lines.append(f"  - {verify['detail']}")
