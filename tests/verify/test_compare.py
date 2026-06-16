"""Tests for value-free sampled-row comparison."""

from __future__ import annotations

from privaci.verify.compare import compare_sampled_rows
from privaci.verify.models import Verdict


def _verdict(results: list, check: str, target: str) -> Verdict:
    for result in results:
        if result.check == check and result.target == target:
            return result.verdict
    raise AssertionError(f"no result for {check} {target}")


def test_unchanged_masked_column_fails() -> None:
    # Arrange — ip_address "masked" but identical in target (the regression bug)
    source = [{"id": 1, "ip_address": "10.0.0.1"}, {"id": 2, "ip_address": "10.0.0.2"}]
    target = [{"id": 1, "ip_address": "10.0.0.1"}, {"id": 2, "ip_address": "10.0.0.2"}]

    # Act
    results = compare_sampled_rows(
        "auth.sessions",
        source,
        target,
        pk=("id",),
        masked_columns={"ip_address"},
        passthrough_columns={"id"},
    )

    # Assert
    assert _verdict(results, "column.change_rate", "auth.sessions.ip_address") is (
        Verdict.FAIL
    )


def test_fully_masked_column_passes() -> None:
    # Arrange
    source = [{"id": 1, "email": "a@x.com"}, {"id": 2, "email": "b@x.com"}]
    target = [{"id": 1, "email": "fake1@t.net"}, {"id": 2, "email": "fake2@t.net"}]

    # Act
    results = compare_sampled_rows(
        "public.users",
        source,
        target,
        pk=("id",),
        masked_columns={"email"},
        passthrough_columns={"id"},
    )

    # Assert
    assert _verdict(results, "column.change_rate", "public.users.email") is Verdict.PASS


def test_surviving_original_warns() -> None:
    # Arrange — one original value survived unchanged at its own row
    source = [{"id": 1, "email": "keep@x.com"}, {"id": 2, "email": "b@x.com"}]
    target = [{"id": 1, "email": "keep@x.com"}, {"id": 2, "email": "fake@t.net"}]

    # Act
    results = compare_sampled_rows(
        "public.users",
        source,
        target,
        pk=("id",),
        masked_columns={"email"},
        passthrough_columns={"id"},
    )

    # Assert
    assert _verdict(results, "column.change_rate", "public.users.email") is Verdict.WARN


def test_passthrough_drift_fails() -> None:
    # Arrange
    source = [{"id": 1, "status": "active"}]
    target = [{"id": 1, "status": "changed"}]

    # Act
    results = compare_sampled_rows(
        "public.users",
        source,
        target,
        pk=("id",),
        masked_columns=set(),
        passthrough_columns={"id", "status"},
    )

    # Assert
    assert (
        _verdict(results, "column.passthrough_drift", "public.users.status")
        is Verdict.FAIL
    )


def test_no_pk_warns() -> None:
    # Act
    results = compare_sampled_rows(
        "audit.events",
        [{"a": 1}],
        [{"a": 1}],
        pk=(),
        masked_columns=set(),
        passthrough_columns={"a"},
    )

    # Assert
    assert results[0].verdict is Verdict.WARN


def test_partial_change_warns() -> None:
    # Arrange — half the masked values unchanged
    source = [{"id": 1, "phone": "111"}, {"id": 2, "phone": "222"}]
    target = [{"id": 1, "phone": "999"}, {"id": 2, "phone": "222"}]

    # Act
    results = compare_sampled_rows(
        "public.users",
        source,
        target,
        pk=("id",),
        masked_columns={"phone"},
        passthrough_columns={"id"},
    )

    # Assert
    assert _verdict(results, "column.change_rate", "public.users.phone") is Verdict.WARN
