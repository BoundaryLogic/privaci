#!/usr/bin/env python3
"""Enforce file (400) and function (40) line limits under ``src/privaci/``.

Waivers:
  - ``# FILE_LIMIT_WAIVER: issue #N`` on the line before an oversized function
  - ``scripts/file_limit_waivers.txt`` entries: ``path`` (file size only) or
    ``path:function`` followed by ``# issue #N``

Run: ``python scripts/check_file_limits.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_gate_common import report_errors
from file_limit_lib import (
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
    collect_violations,
    format_violations,
)


def main() -> int:
    """CLI entrypoint."""
    try:
        violations = collect_violations()
    except ValueError as exc:
        return report_errors("File-limit waiver parse failed", [str(exc)])
    return report_errors(
        "File/function line limits exceeded "
        f"(max {MAX_FILE_LINES} lines/file, {MAX_FUNCTION_LINES} lines/function). "
        "Add an issue-linked waiver or refactor. See docs/ci-gates.md",
        format_violations(violations),
    )


if __name__ == "__main__":
    raise SystemExit(main())
