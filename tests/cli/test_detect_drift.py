"""Tests for ``privaci detect-drift`` CLI wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from privaci.cli._detect_drift import execute_detect_drift
from privaci.cli._errors import run_cli
from privaci.contracts.base import DriftReport


def test_detect_drift_exits_6_when_drift_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DB_URL", "postgresql://u:p@localhost/source")
    monkeypatch.setenv("TARGET_DB_URL", "postgresql://u:p@localhost/target")
    report = DriftReport(
        has_drift=True,
        findings=[{"kind": "column_added", "table": "public.users", "column": "x"}],
    )

    with patch("privaci.cli._detect_drift._detect_async", return_value=report):
        exit_code = run_cli(
            lambda: execute_detect_drift(source=None, target=None, accept_drift=False)
        )

    assert exit_code == 6


def test_detect_drift_accept_drift_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DB_URL", "postgresql://u:p@localhost/source")
    monkeypatch.setenv("TARGET_DB_URL", "postgresql://u:p@localhost/target")
    report = DriftReport(
        has_drift=True, findings=[{"kind": "table_added", "table": "t"}]
    )

    with patch("privaci.cli._detect_drift._detect_async", return_value=report):
        exit_code = run_cli(
            lambda: execute_detect_drift(source=None, target=None, accept_drift=True)
        )

    assert exit_code == 0
