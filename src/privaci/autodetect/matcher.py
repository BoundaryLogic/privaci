"""Column-name pattern matching for auto-detect."""

from __future__ import annotations

import re
from typing import get_args

from privaci.autodetect.patterns import (
    BUILTIN_PATTERNS,
    PatternKind,
    PatternRule,
    compile_patterns,
)


def match_column_name(column_name: str) -> PatternRule | None:
    """Return the first pattern rule matching ``column_name``, if any.

    Rules are evaluated in library order; earlier rules win.
    """
    lowered = column_name.lower()
    compiled = compile_patterns()
    for rule in BUILTIN_PATTERNS:
        if _rule_matches(lowered, rule, compiled):
            return rule
    return None


def _delimiter_bounded_substring(lowered: str, needle: str) -> bool:
    """Match ``needle`` only at underscore boundaries or as the whole name."""
    if lowered == needle:
        return True
    padded = f"_{lowered}_"
    return f"_{needle}_" in padded


def _rule_matches(
    lowered: str,
    rule: PatternRule,
    compiled: dict[str, re.Pattern[str]],
) -> bool:
    kind = rule.kind
    if kind == "substring":
        return rule.pattern in lowered
    elif kind == "bounded_substring":
        return _delimiter_bounded_substring(lowered, rule.pattern)
    elif kind == "suffix":
        return lowered.endswith(rule.pattern)
    elif kind in ("prefix", "wildcard_prefix"):
        return lowered.startswith(rule.pattern)
    elif kind == "regex":
        pattern = compiled.get(rule.rule_id)
        return pattern is not None and pattern.fullmatch(lowered) is not None
    # CodeQL's mixed-return rule wants an explicit non-returning terminal rather
    # than an implicit fall-through after the exhaustive ``kind`` chain above.
    # Derive the valid kinds from PatternKind so the message can never drift.
    expected = ", ".join(get_args(PatternKind))
    msg = f"Unknown auto-detect pattern kind: {kind!r}. Expected one of: {expected}."
    raise ValueError(msg)
