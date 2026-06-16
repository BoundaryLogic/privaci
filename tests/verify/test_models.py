"""Tests for value-free verification result models."""

from __future__ import annotations

from privaci.verify.models import CheckResult, Verdict, VerifyReport


def test_check_result_repr() -> None:
    # Arrange
    result = CheckResult("column.change_rate", Verdict.PASS, "public.users.email", "ok")

    # Act & Assert
    assert repr(result) == (
        "CheckResult('column.change_rate', pass, 'public.users.email')"
    )


def test_verify_report_filters_and_counts() -> None:
    # Arrange
    results = (
        CheckResult("a", Verdict.PASS, "t1", "ok"),
        CheckResult("b", Verdict.WARN, "t2", "maybe"),
        CheckResult("c", Verdict.FAIL, "t3", "bad"),
    )
    report = VerifyReport(results=results)

    # Assert
    assert len(report.failed) == 1
    assert len(report.warnings) == 1
    assert not report.is_ok
    counts = report.counts()
    assert counts[Verdict.PASS] == 1
    assert counts[Verdict.WARN] == 1
    assert counts[Verdict.FAIL] == 1
    assert "fail=1" in repr(report)


def test_verify_report_is_ok_when_no_failures() -> None:
    # Arrange
    report = VerifyReport(
        results=(CheckResult("a", Verdict.WARN, "t", "review"),),
    )

    # Assert
    assert report.is_ok
