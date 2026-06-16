"""Freeform-text shape and confidence scoring."""

from __future__ import annotations

import re

from privaci.autodetect.models import DetectionConfidence
from privaci.autodetect.table_context import table_sensitivity
from privaci.catalog.models import ColumnInfo

_FREEFORM_MIN_AVG_WIDTH = 200
_FREEFORM_UNCERTAIN_MIN_AVG_WIDTH = 100
_TEXT_TYPES = frozenset({"text"})
_VARCHAR_RE = re.compile(r"^character varying\((\d+)\)$", re.IGNORECASE)


def is_freeform_eligible_type(column: ColumnInfo) -> bool:
    """Return whether the column type can hold narrative freeform text."""
    base = _base_type(column.data_type)
    if base in _TEXT_TYPES:
        return True
    match = _VARCHAR_RE.match(column.data_type.strip())
    if match is None:
        return False
    return int(match.group(1)) >= 500


def score_freeform_confidence(
    *,
    table_name: str,
    column: ColumnInfo,
) -> tuple[DetectionConfidence, tuple[str, ...]]:
    """Score a freeform name-match using type, stats, and table context."""
    reasons: list[str] = []
    if not is_freeform_eligible_type(column):
        reasons.append(f"type {column.data_type!r} is not freeform-eligible")
        return "low", tuple(reasons)

    reasons.append("column type is freeform-eligible")
    sensitivity = table_sensitivity(table_name)
    avg_width = column.avg_width

    if avg_width is None:
        reasons.append("pg_stats.avg_width unavailable")
        if sensitivity == "sensitive":
            reasons.append("sensitive table context")
            return "medium", tuple(reasons)
        return "low", tuple(reasons)

    reasons.append(f"pg_stats.avg_width={avg_width:.0f}")
    if avg_width >= _FREEFORM_MIN_AVG_WIDTH:
        if sensitivity == "low":
            reasons.append("low-sensitivity table context downgrades confidence")
            return "medium", tuple(reasons)
        if sensitivity == "sensitive":
            reasons.append("sensitive table context")
        return "high", tuple(reasons)

    if avg_width >= _FREEFORM_UNCERTAIN_MIN_AVG_WIDTH and sensitivity == "sensitive":
        reasons.append("borderline avg_width on sensitive table")
        return "medium", tuple(reasons)

    reasons.append("avg_width below freeform threshold")
    return "low", tuple(reasons)


def _base_type(data_type: str) -> str:
    return re.sub(r"\(.*\)$", "", data_type.strip().lower())
