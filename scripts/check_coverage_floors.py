#!/usr/bin/env python3
"""Fail if critical package coverage falls below floors in ci-gates-floors.toml.

Expects a fresh ``.coverage`` from pytest ``--cov=src``.

Usage::

  python scripts/check_coverage_floors.py
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_gate_common import report_errors

ROOT = Path(__file__).resolve().parents[1]
FLOORS_PATH = ROOT / "docs" / "ci-gates-floors.toml"


def _load_floors() -> dict[str, int]:
    """Load include-glob → floor percent from ``docs/ci-gates-floors.toml``.

    Keys must already be coverage ``--include`` globs ending in ``/*``.
    Directory-style keys are rejected (no silent rewrite).
    """
    if not FLOORS_PATH.is_file():
        raise FileNotFoundError(f"missing floors file {FLOORS_PATH}")
    raw = tomllib.loads(FLOORS_PATH.read_text(encoding="utf-8"))
    floors_raw = raw.get("floors")
    if not isinstance(floors_raw, dict) or not floors_raw:
        raise ValueError(f"{FLOORS_PATH} missing [floors] table")
    floors: dict[str, int] = {}
    for key, value in floors_raw.items():
        path = str(key).strip().strip("\"'")
        if not path.endswith("/*"):
            raise ValueError(
                f"floor key {path!r} must be a coverage include glob ending "
                f"in '/*' (e.g. 'src/privaci/mask/*')"
            )
        floors[path] = int(value)
    return floors


def main() -> int:
    """Return 0 when every critical floor passes."""
    if not (ROOT / ".coverage").is_file():
        return report_errors(
            "Coverage floors check failed",
            [".coverage missing — run pytest --cov=src first"],
        )
    try:
        floors = _load_floors()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return report_errors("Coverage floors check failed", [str(exc)])
    failed: list[str] = []
    for include, floor in floors.items():
        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "report",
            f"--include={include}",
            f"--fail-under={floor}",
        ]
        print(f"coverage floor check: {include} ≥ {floor}%")
        # SECURITY: argv is fixed coverage CLI + floor keys from trusted TOML.
        result = subprocess.run(cmd, cwd=ROOT, check=False)  # noqa: S603
        if result.returncode != 0:
            failed.append(f"{include} below floor {floor}%")
    return report_errors("Coverage floors check failed", failed)


if __name__ == "__main__":
    raise SystemExit(main())
