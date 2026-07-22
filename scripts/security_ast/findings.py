"""Finding model for the security AST gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Finding:
    """One security AST finding."""

    rel_path: str
    line: int
    rule: str
    detail: str
    symbol: str | None = None


def format_findings(findings: list[Finding]) -> list[str]:
    """Render findings as human-readable error strings."""
    return [
        f"{item.rel_path}:{item.line} [{item.rule}] {item.detail}" for item in findings
    ]
