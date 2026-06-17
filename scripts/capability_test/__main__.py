"""Capability test CLI — selective public/commercial verification with report."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.capability_test.compose_dev import (
    DEFAULT_SOURCE,
    DEFAULT_TARGET,
    compose_dev_down,
    compose_dev_up,
    engine_root,
    wait_postgres_ready,
)
from scripts.capability_test.guard import (
    ResourceGuardError,
    check_memory_or_raise,
    heavy_work_confirmed,
    mem_available_mb,
    require_heavy_confirmation,
    swap_used_pct,
)
from scripts.capability_test.nlp import (
    check_spacy_ner,
    require_spacy_ner_for_capabilities,
)
from scripts.capability_test.registry import (
    CAPABILITIES,
    CAPABILITY_GROUPS,
    CAPABILITY_SUITES,
    Capability,
    CapabilitySuite,
    resolve_capability_ids,
)
from scripts.capability_test.report import build_report_payload, write_reports
from scripts.capability_test.runner import (
    CapabilityResult,
    run_capability,
    summarize_results,
)

_HEAVY_GROUPS = frozenset(
    {
        "all",
        "all-public",
        "all-commercial",
        "public-integration",
        "commercial-integration",
    }
)
_DEFAULT_UNIT_TIMEOUT = 90
_DEFAULT_INTEGRATION_TIMEOUT = 120


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run selected PrivaCI capabilities with resource guards. "
            "Unit tests are safe by default; Postgres/integration require "
            "--allow-heavy and healthy memory."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List capability ids, groups, and descriptions.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show what would run and memory status; do not execute.",
    )
    parser.add_argument(
        "--cap",
        dest="capabilities",
        action="append",
        default=[],
        metavar="ID",
        help=(
            "Capability id or group (repeatable, comma-separated). Groups: "
            + ", ".join(sorted(CAPABILITY_GROUPS))
        ),
    )
    parser.add_argument(
        "--allow-heavy",
        action="store_true",
        help=(
            "Required for integration tests, compose up, volume reset, or "
            "running more than two capabilities. Refused when swap is high."
        ),
    )
    parser.add_argument(
        "--prep-only",
        action="store_true",
        help="Start compose.dev.yml Postgres and exit (requires --allow-heavy).",
    )
    parser.add_argument(
        "--no-compose",
        action="store_true",
        help="Skip compose up; use existing Postgres on 55432/55433.",
    )
    parser.add_argument(
        "--reset-volumes",
        action="store_true",
        help="compose down -v before up (requires --allow-heavy).",
    )
    parser.add_argument(
        "--down",
        action="store_true",
        help="Stop compose.dev.yml after the run.",
    )
    parser.add_argument(
        "--down-volumes",
        action="store_true",
        help="Stop compose.dev.yml and remove volumes after the run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/capability-tests"),
        help="Directory for JSON + Markdown reports.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_UNIT_TIMEOUT,
        help=f"Per-capability pytest timeout seconds (default: {_DEFAULT_UNIT_TIMEOUT}).",
    )
    parser.add_argument(
        "--suite",
        metavar="ID",
        choices=sorted(CAPABILITY_SUITES),
        help=(
            "Run a predefined multi-phase suite (quick, public, commercial, "
            "standard, full). Mutually exclusive with --cap."
        ),
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip post-run Postgres validation checks.",
    )
    return parser


def _expand_suite_phases(
    suite: CapabilitySuite,
) -> list[tuple[tuple[str, ...], list[Capability]]]:
    """Return ordered phases of capabilities (de-duplicated globally)."""
    seen: set[str] = set()
    phases: list[tuple[tuple[str, ...], list[Capability]]] = []
    for groups in suite.phases:
        caps: list[Capability] = []
        for cid in resolve_capability_ids(list(groups)):
            if cid in seen:
                continue
            seen.add(cid)
            caps.append(CAPABILITIES[cid])
        phases.append((groups, caps))
    return phases


def _print_metrics_line(result) -> None:
    if result.metrics is None:
        return
    print(f"   metrics: {result.metrics.summary}", flush=True)
    fk_checks = result.metrics.data.get("fk_checks")
    if fk_checks:
        passed = sum(1 for c in fk_checks if c.get("passed"))
        print(f"   fk checks: {passed}/{len(fk_checks)} passed", flush=True)


def _capability_run_order(cap: Capability) -> tuple[int, str]:
    if cap.id == "public-spacy-ner":
        return (0, cap.id)
    if cap.requires_nlp:
        return (1, cap.id)
    return (2, cap.id)


def _run_capability_batch(
    caps: list[Capability],
    args: argparse.Namespace,
) -> list[CapabilityResult]:
    results = []
    for cap in sorted(caps, key=_capability_run_order):
        print(f">> {cap.id} ({cap.label})", flush=True)
        result = run_capability(
            cap,
            timeout_sec=_timeout_for(cap, args.timeout),
            skip_validate=args.skip_validate,
        )
        results.append(result)
        print(f"   {result.status} ({result.duration_sec}s)", flush=True)
        _print_metrics_line(result)
        if cap.requires_postgres:
            check_memory_or_raise()
    return results


def _print_catalog() -> None:
    print("Capability suites:")
    for sid, suite in sorted(CAPABILITY_SUITES.items()):
        heavy = " [HEAVY]" if suite.requires_heavy else ""
        phase_desc = " → ".join(", ".join(g) for g in suite.phases)
        print(f"  {sid}{heavy}: {suite.description}")
        print(f"    phases: {phase_desc}")
    print("\nCapability groups:")
    for name, members in sorted(CAPABILITY_GROUPS.items()):
        heavy = " [HEAVY]" if name in _HEAVY_GROUPS else ""
        print(f"  {name}{heavy}: {', '.join(sorted(members))}")
    print("\nCapabilities:")
    for cid, cap in sorted(CAPABILITIES.items()):
        flags = []
        if cap.requires_postgres:
            flags.append("HEAVY/postgres")
        if cap.requires_nlp:
            flags.append("nlp")
        if cap.requires_commercial_env:
            flags.append("commercial-env")
        tag = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {cid}{tag}")
        print(f"    {cap.label} — {cap.description}")
    print(
        "\nSafe (unit-only) example:\n"
        "  ./scripts/capability-test.sh --cap public-detect-drift,commercial-jsonb-transform"
    )
    print("\nSuite example (unit only):\n" "  ./scripts/capability-test-suite.sh quick")
    print(
        "\nFull validation (requires --allow-heavy):\n"
        "  ./scripts/capability-test-suite.sh standard --allow-heavy --reset-volumes"
    )


def _is_heavy_request(
    caps: list[Capability],
    *,
    capabilities_raw: list[str],
    prep_only: bool,
    reset_volumes: bool,
) -> bool:
    if prep_only or reset_volumes:
        return True
    if any(cap.requires_postgres for cap in caps):
        return True
    if len(caps) > 2:
        return True
    for token in capabilities_raw:
        for part in token.split(","):
            part = part.strip()
            if part in _HEAVY_GROUPS:
                return True
    return False


def _timeout_for(cap: Capability, user_timeout: int) -> int:
    if cap.requires_postgres:
        return max(user_timeout, _DEFAULT_INTEGRATION_TIMEOUT)
    return user_timeout


def _print_plan(
    *,
    selected: list[str],
    caps: list[Capability],
    heavy: bool,
    args: argparse.Namespace,
) -> None:
    avail = mem_available_mb()
    swap = swap_used_pct()
    print(f"MemAvailable: {avail}MB · Swap used: {swap}%")
    print(f"Heavy request: {heavy} · --allow-heavy: {args.allow_heavy}")
    print(f"Selected ({len(caps)}):")
    for cap in caps:
        mark = "HEAVY" if cap.requires_postgres else "unit"
        print(f"  - {cap.id} [{mark}]")
    if heavy and not args.allow_heavy:
        print("\nWould REFUSE: pass --allow-heavy to run this plan.")
    elif heavy:
        print("\nWould run after memory check (needs healthy swap/RAM).")
    else:
        print("\nWould run (unit-only).")


def _prep_nlp(caps: list[Capability]) -> list[str]:
    nlp_caps = tuple(cap.id for cap in caps if cap.requires_nlp)
    if not nlp_caps:
        return []
    require_spacy_ner_for_capabilities(capability_ids=nlp_caps)
    _ready, detail = check_spacy_ner()
    return [detail]


def _prep_postgres(*, reset_volumes: bool, no_compose: bool) -> list[str]:
    logs: list[str] = []
    if no_compose:
        logs.append("Skipping compose (--no-compose); probing existing Postgres.")
    else:
        logs.extend(compose_dev_up(reset_volumes=reset_volumes))
    logs.extend(wait_postgres_ready(DEFAULT_SOURCE, DEFAULT_TARGET))
    return logs


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m scripts.capability_test``."""
    args = _build_parser().parse_args(argv)
    if args.list:
        _print_catalog()
        return 0

    if args.allow_heavy:
        os.environ["CAPABILITY_ALLOW_HEAVY"] = "1"

    if args.suite and args.capabilities:
        print("ERROR: use either --suite or --cap, not both.", file=sys.stderr)
        return 2

    if not args.capabilities and not args.prep_only and not args.suite:
        print(
            "ERROR: pass --cap ID/group, --suite ID, or --prep-only (or use --list).",
            file=sys.stderr,
        )
        return 2

    suite_id: str | None = args.suite
    suite_phases_meta: list[dict] = []
    phase_batches: list[tuple[tuple[str, ...], list[Capability]]] = []

    if suite_id:
        suite = CAPABILITY_SUITES[suite_id]
        phase_batches = _expand_suite_phases(suite)
        selected = [cap.id for _, batch in phase_batches for cap in batch]
        caps = [CAPABILITIES[cid] for cid in selected]
        heavy = suite.requires_heavy or args.prep_only or args.reset_volumes
    else:
        selected = []
        if args.capabilities:
            try:
                selected = resolve_capability_ids(args.capabilities)
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
        caps = [CAPABILITIES[cid] for cid in selected]
        heavy = _is_heavy_request(
            caps,
            capabilities_raw=args.capabilities,
            prep_only=args.prep_only,
            reset_volumes=args.reset_volumes,
        )
        phase_batches = [(tuple(), caps)]

    if args.plan:
        _print_plan(selected=selected, caps=caps, heavy=heavy, args=args)
        if suite_id:
            print(f"\nSuite: {suite_id} ({len(phase_batches)} phase(s))")
            for idx, (groups, batch) in enumerate(phase_batches, start=1):
                print(
                    f"  Phase {idx}: {', '.join(groups) or 'custom'} ({len(batch)} caps)"
                )
        return 0

    try:
        check_memory_or_raise(
            min_avail_mb=2048 if not heavy else 4096,
        )
        if heavy:
            require_heavy_confirmation(
                reason="Postgres compose and/or integration tests requested.",
            )
    except ResourceGuardError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    needs_postgres = any(cap.requires_postgres for cap in caps)
    needs_nlp = any(cap.requires_nlp for cap in caps)
    prep_logs: list[str] = []
    postgres_ready = False

    if needs_nlp:
        try:
            prep_logs.extend(_prep_nlp(caps))
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.prep_only or needs_postgres:
        try:
            prep_logs = _prep_postgres(
                reset_volumes=args.reset_volumes,
                no_compose=args.no_compose,
            )
            postgres_ready = True
        except (RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
            print(f"ERROR: prep failed: {exc}", file=sys.stderr)
            return 1

    if args.prep_only:
        print("Postgres ready (--prep-only).")
        for line in prep_logs:
            print(line)
        return 0

    results = []
    for phase_idx, (groups, batch) in enumerate(phase_batches, start=1):
        if len(phase_batches) > 1:
            label = ", ".join(groups) if groups else "run"
            print(
                f"\n== Phase {phase_idx}/{len(phase_batches)}: {label} ==", flush=True
            )
            suite_phases_meta.append(
                {
                    "index": phase_idx,
                    "groups": list(groups),
                    "capability_count": len(batch),
                }
            )
        if any(c.requires_postgres for c in batch) and not postgres_ready:
            try:
                prep_logs.extend(
                    _prep_postgres(
                        reset_volumes=args.reset_volumes,
                        no_compose=args.no_compose,
                    )
                )
                postgres_ready = True
            except (RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
                print(f"ERROR: prep failed: {exc}", file=sys.stderr)
                return 1
        results.extend(_run_capability_batch(batch, args))

    env_snapshot = {
        "engine_root": str(engine_root()),
        "source_db_url": DEFAULT_SOURCE,
        "target_db_url": DEFAULT_TARGET,
        "mem_available_mb": mem_available_mb(),
        "swap_used_pct": swap_used_pct(),
        "heavy": heavy,
        "allow_heavy": heavy_work_confirmed(),
    }
    output_dir = args.output_dir.expanduser().resolve()
    payload = build_report_payload(
        results=results,
        prep_logs=prep_logs,
        selected=selected,
        environment=env_snapshot,
        suite=suite_id,
        suite_phases=suite_phases_meta or None,
    )
    json_path, md_path = write_reports(payload, output_dir)
    summary = summarize_results(results)
    print("")
    print(
        f"Done: {summary.get('passed', 0)} passed, "
        f"{summary.get('failed', 0)} failed, "
        f"{summary.get('warn', 0)} warn, "
        f"{summary.get('error', 0)} error(s)."
    )
    print(f"Report (JSON):     {json_path.resolve()}")
    print(f"Report (Markdown): {md_path.resolve()}")

    if args.down or args.down_volumes:
        compose_dev_down(volumes=args.down_volumes)

    has_failures = summary.get("failed", 0) > 0 or summary.get("error", 0) > 0
    return 0 if not has_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
