#!/usr/bin/env python3
"""Security AST guard for mask/stream/secrets/config/pipeline packages.

Checks:
  - ``eval`` / ``exec`` / ``__import__`` calls
  - ``subprocess`` invocations with ``shell=True``
  - Heuristic SQL string concatenation near DB execute/fetch helpers
  - Logger interpolation / PII-ish positional names (Article III / D7)
  - Article I: HTTP client imports in mask/stream/pipeline
  - Packaging package imports (``privaci_commercial``) anywhere under ``src/privaci``

Allowlist: ``scripts/security_ast_allowlist.txt`` entries
``path:lineno`` or ``path:symbol`` followed by ``# issue #N``.

Run: ``python scripts/check_security_ast.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_gate_common import report_errors
from security_ast import collect_findings, format_findings


def main() -> int:
    """CLI entrypoint."""
    try:
        findings = collect_findings()
    except ValueError as exc:
        return report_errors("Security AST allowlist parse failed", [str(exc)])
    return report_errors(
        "Security AST check failed. Fix the finding or add an issue-linked "
        "allowlist entry. See docs/ci-gates.md",
        format_findings(findings),
    )


if __name__ == "__main__":
    raise SystemExit(main())
