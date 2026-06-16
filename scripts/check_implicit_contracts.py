#!/usr/bin/env python3
"""Release guard: validate implicit contracts the commercial layer depends on.

The commercial tier pins to the engine's ABC surface via ``CONTRACT_VERSION``,
but also relies on shapes that are not ABC methods:

- ``_privaci.runs.source_db_hash`` and ``source_schema_snapshot`` columns
- ``LicenseError`` exit code ``5`` and ``DriftError`` exit code ``6``
- The canonical catalog snapshot JSON shape persisted at run time

Run: ``python scripts/check_implicit_contracts.py``
Optional: ``python scripts/check_implicit_contracts.py --fixture PATH``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from privaci.errors import DriftError, LicenseError
from privaci.state.ddl import CREATE_RUNS_SQL

_REQUIRED_RUNS_COLUMNS = frozenset({"source_db_hash", "source_schema_snapshot"})
_EXPECTED_EXIT_CODES: dict[str, int] = {
    "LicenseError": 5,
    "DriftError": 6,
}
_REQUIRED_COLUMN_KEYS = frozenset({"name", "data_type"})


def validate_runs_ddl() -> None:
    """Raise ``ValueError`` when required ``_privaci.runs`` columns are absent."""
    missing = sorted(
        column for column in _REQUIRED_RUNS_COLUMNS if column not in CREATE_RUNS_SQL
    )
    if missing:
        msg = f"_privaci.runs DDL is missing required column(s): {', '.join(missing)}"
        raise ValueError(msg)


def validate_exit_codes() -> None:
    """Raise ``ValueError`` when commercial exit codes drift."""
    actual = {
        "LicenseError": LicenseError.exit_code,
        "DriftError": DriftError.exit_code,
    }
    for name, expected in _EXPECTED_EXIT_CODES.items():
        found = actual[name]
        if found != expected:
            msg = f"{name}.exit_code is {found}, expected {expected}"
            raise ValueError(msg)


def _column_map(table: dict[str, Any]) -> dict[str, str]:
    """Normalize engine snapshot columns to name → data_type."""
    columns = table.get("columns")
    if isinstance(columns, list):
        result: dict[str, str] = {}
        for entry in columns:
            if not isinstance(entry, dict):
                msg = "snapshot column entry must be an object"
                raise ValueError(msg)
            missing = _REQUIRED_COLUMN_KEYS - entry.keys()
            if missing:
                msg = f"snapshot column entry missing keys: {sorted(missing)}"
                raise ValueError(msg)
            result[str(entry["name"])] = str(entry["data_type"])
        return result
    if isinstance(columns, dict):
        return {str(name): str(dtype) for name, dtype in columns.items()}
    msg = f"unsupported snapshot columns type: {type(columns).__name__}"
    raise ValueError(msg)


def validate_snapshot_fixture(path: Path) -> None:
    """Raise ``ValueError`` when the fixture is not engine-canonical shape."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload.get("tables")
    if not isinstance(tables, dict) or not tables:
        msg = "snapshot fixture must contain a non-empty tables object"
        raise ValueError(msg)
    for table_id, table in tables.items():
        if not isinstance(table, dict):
            msg = f"table {table_id!r} must be an object"
            raise ValueError(msg)
        _column_map(table)


def main(argv: list[str] | None = None) -> int:
    """Return 0 when all implicit contracts hold."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/canonical_catalog_snapshot.json"),
        help="Canonical catalog snapshot JSON to validate (default: engine fixture).",
    )
    args = parser.parse_args(argv)
    try:
        validate_runs_ddl()
        validate_exit_codes()
        validate_snapshot_fixture(args.fixture)
    except ValueError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
