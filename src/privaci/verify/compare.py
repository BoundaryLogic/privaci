"""Pure, value-free comparison of sampled source and target rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from privaci.verify.models import CheckResult, Verdict


@dataclass(frozen=True, slots=True)
class ColumnStats:
    """Accumulated per-column comparison counts (no raw values)."""

    total: int = 0
    changed: int = 0
    both_null: int = 0


def compare_sampled_rows(
    table_id: str,
    source_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    *,
    pk: tuple[str, ...],
    masked_columns: set[str],
    passthrough_columns: set[str],
) -> list[CheckResult]:
    """Compare PK-matched source/target rows and return value-free verdicts."""
    if not pk:
        return [
            CheckResult(
                "table.no_pk",
                Verdict.WARN,
                table_id,
                "No single/whole primary key; row-level checks skipped.",
            )
        ]
    matched = _match_rows_by_pk(source_rows, target_rows, pk)
    if not matched:
        return [
            CheckResult(
                "table.sample_match",
                Verdict.WARN,
                table_id,
                "No sampled source rows matched target by primary key.",
            )
        ]
    columns = set(source_rows[0]) if source_rows else set()
    results: list[CheckResult] = []
    for column in sorted(columns):
        stats = _column_stats(matched, column)
        if column in masked_columns:
            results.append(_masked_verdict(table_id, column, stats))
        elif column in passthrough_columns:
            results.append(_passthrough_verdict(table_id, column, stats))
    return results


def _match_rows_by_pk(
    source_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    pk: tuple[str, ...],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    target_index = {_pk_key(row, pk): row for row in target_rows}
    return [
        (src, target_index[_pk_key(src, pk)])
        for src in source_rows
        if _pk_key(src, pk) in target_index
    ]


def _pk_key(row: dict[str, Any], pk: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(name) for name in pk)


def _column_stats(
    matched: list[tuple[dict[str, Any], dict[str, Any]]],
    column: str,
) -> ColumnStats:
    total = changed = both_null = 0
    for src, tgt in matched:
        src_val = src.get(column)
        tgt_val = tgt.get(column)
        total += 1
        if src_val is None and tgt_val is None:
            both_null += 1
            continue
        if str(src_val) != str(tgt_val):
            changed += 1
    return ColumnStats(total=total, changed=changed, both_null=both_null)


def _masked_verdict(table_id: str, column: str, stats: ColumnStats) -> CheckResult:
    target = f"{table_id}.{column}"
    comparable = stats.total - stats.both_null
    if comparable == 0:
        return CheckResult(
            "column.change_rate",
            Verdict.WARN,
            target,
            "All sampled values are NULL; cannot assess masking.",
        )
    if stats.changed == 0:
        return CheckResult(
            "column.change_rate",
            Verdict.FAIL,
            target,
            "Masked column unchanged in all sampled rows (mask not applied?).",
        )
    if stats.changed < comparable:
        rate = stats.changed / comparable
        unchanged = comparable - stats.changed
        return CheckResult(
            "column.change_rate",
            Verdict.WARN,
            target,
            f"Only {rate:.0%} of sampled values changed; "
            f"{unchanged} original value(s) survived.",
        )
    return CheckResult(
        "column.change_rate",
        Verdict.PASS,
        target,
        f"All {comparable} sampled value(s) changed.",
    )


def _passthrough_verdict(table_id: str, column: str, stats: ColumnStats) -> CheckResult:
    target = f"{table_id}.{column}"
    if stats.changed > 0:
        return CheckResult(
            "column.passthrough_drift",
            Verdict.FAIL,
            target,
            f"{stats.changed} passthrough value(s) changed unexpectedly.",
        )
    return CheckResult(
        "column.passthrough_drift",
        Verdict.PASS,
        target,
        "Passthrough column unchanged.",
    )
