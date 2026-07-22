#!/usr/bin/env python3
"""Fail relative Markdown links that leave ``docs/`` (MkDocs --strict parity).

MkDocs ``--strict`` treats only files under ``docs/`` as documentation. A
relative link like ``../CONSTITUTION.md`` resolves on disk but fails the site
build. Absolute ``http(s):`` links are allowed for out-of-tree repo files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ci_gate_common import report_errors

# [text](target) — ignore images ![...](...) by requiring non-! before '['.
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")


def _is_external(target: str) -> bool:
    lower = target.lower()
    return (
        lower.startswith("http://")
        or lower.startswith("https://")
        or lower.startswith("mailto:")
        or target.startswith("#")
    )


def _link_target(raw: str) -> str:
    """Strip optional title and fragment from a Markdown link destination."""
    target = raw.strip().split()[0].strip("<>")
    if "#" in target:
        target = target.split("#", 1)[0]
    return target


def collect_out_of_docs_links(docs_root: Path) -> list[str]:
    """Return findings for relative links that resolve outside ``docs_root``."""
    docs_root = docs_root.resolve()
    findings: list[str] = []
    for path in sorted(docs_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in _LINK_RE.finditer(text):
            dest = _link_target(match.group(2))
            if not dest or _is_external(dest):
                continue
            resolved = (path.parent / dest).resolve()
            try:
                resolved.relative_to(docs_root)
            except ValueError:
                rel = path.relative_to(docs_root)
                findings.append(
                    f"{rel}: relative link '{dest}' leaves docs/ "
                    "(use a path under docs/ or an absolute https URL)"
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    """CLI entry: scan ``docs/`` for out-of-tree relative links."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Docs directory (default: <repo>/docs)",
    )
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    docs_root = args.docs_root or (repo / "docs")
    if not docs_root.is_dir():
        return report_errors(
            "MkDocs doc-link check failed.",
            [f"docs root missing: {docs_root}"],
        )
    findings = collect_out_of_docs_links(docs_root)
    return report_errors(
        "MkDocs doc-link check failed (relative links must stay under docs/).",
        findings,
    )


if __name__ == "__main__":
    sys.exit(main())
