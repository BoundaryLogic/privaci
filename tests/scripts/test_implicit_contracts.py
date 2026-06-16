"""Tests for the implicit commercial-contract guard script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(filename: str):
    path = _REPO_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_guard = _load_script_module("check_implicit_contracts.py")
_FIXTURE = _REPO_ROOT / "tests/fixtures/canonical_catalog_snapshot.json"


def test_implicit_contract_guard_passes_on_repo_fixture() -> None:
    # Act / Assert
    _guard.validate_runs_ddl()
    _guard.validate_exit_codes()
    _guard.validate_snapshot_fixture(_FIXTURE)


def test_validate_runs_ddl_rejects_missing_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    broken = "CREATE TABLE _privaci.runs (run_id uuid PRIMARY KEY)"
    monkeypatch.setattr(_guard, "CREATE_RUNS_SQL", broken)

    # Act / Assert
    with pytest.raises(ValueError, match="source_db_hash"):
        _guard.validate_runs_ddl()


def test_validate_snapshot_fixture_rejects_bad_columns(tmp_path: Path) -> None:
    # Arrange
    path = tmp_path / "bad.json"
    path.write_text(
        '{"tables":{"public.users":{"columns":[{"name":"id"}]}}}',
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="data_type"):
        _guard.validate_snapshot_fixture(path)
