#!/usr/bin/env python3
"""Document registry guard (CONSTITUTION Article X).

Validates ``docs/registry.yaml`` structure, package coverage, env-example
documentation, exit-code anchor sync, and code→docs diff coupling.

Run:
  python scripts/check_doc_registry.py              # ci-local (merge-base diff)
  python scripts/check_doc_registry.py --staged     # pre-commit (index only)
  python scripts/check_doc_registry.py --base-sha <sha>  # GitHub PR base
  python scripts/check_doc_registry.py --skip-coupling  # structure-only / main push
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ci_gate_common import report_errors
from doc_registry import run_checks


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Couple against staged files only (pre-commit).",
    )
    parser.add_argument(
        "--base-sha",
        default=None,
        help="Explicit diff base SHA (GitHub PR base.sha per D11).",
    )
    parser.add_argument(
        "--skip-coupling",
        action="store_true",
        help="Skip diff coupling (structure, coverage, env, exit-code sync only).",
    )
    args = parser.parse_args()
    if args.staged and args.base_sha:
        parser.error("--staged and --base-sha are mutually exclusive")
    return report_errors(
        "Document registry check failed (docs/registry.yaml). "
        "Update bound docs (and CHANGELOG when required) or add an issue-linked "
        "waiver on the entry. See docs/ci-gates.md",
        run_checks(
            staged=args.staged,
            skip_coupling=args.skip_coupling,
            base_sha=args.base_sha,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
