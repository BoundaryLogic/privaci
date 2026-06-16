"""Result models for masking verification.

All models are value-free: they carry counts, rates, and column identifiers,
never raw cell values, so a verification report is safe to print anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Verdict(StrEnum):
    """Outcome of a single verification check."""

    PASS = "pass"  # noqa: S105 — verdict label, not a credential
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One verification check outcome.

    Attributes:
        check: Machine-readable check id (e.g. ``column.change_rate``).
        verdict: Pass / warn / fail.
        target: Schema-qualified table or column the check applies to.
        detail: Human-readable, value-free explanation.
    """

    check: str
    verdict: Verdict
    target: str
    detail: str

    def __repr__(self) -> str:
        return f"CheckResult({self.check!r}, {self.verdict}, {self.target!r})"


@dataclass(frozen=True, slots=True)
class VerifyReport:
    """Aggregate verification outcome across all tables."""

    results: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def failed(self) -> tuple[CheckResult, ...]:
        """Return only failing checks."""
        return tuple(r for r in self.results if r.verdict is Verdict.FAIL)

    @property
    def warnings(self) -> tuple[CheckResult, ...]:
        """Return only warning checks."""
        return tuple(r for r in self.results if r.verdict is Verdict.WARN)

    @property
    def is_ok(self) -> bool:
        """Return whether no check failed."""
        return not self.failed

    def counts(self) -> dict[Verdict, int]:
        """Return a verdict → count summary."""
        summary = {verdict: 0 for verdict in Verdict}
        for result in self.results:
            summary[result.verdict] += 1
        return summary

    def __repr__(self) -> str:
        counts = self.counts()
        return (
            f"VerifyReport(pass={counts[Verdict.PASS]}, "
            f"warn={counts[Verdict.WARN]}, fail={counts[Verdict.FAIL]})"
        )
