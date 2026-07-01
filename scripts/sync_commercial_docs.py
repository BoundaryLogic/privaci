#!/usr/bin/env python3
"""Sync publishable commercial docs into ``docs/commercial/`` for MkDocs.

Source of truth: ``privaci-commercial/docs/publishable.txt``. Run from the
public engine repo:

  python scripts/sync_commercial_docs.py --source ../privaci-commercial

CI passes ``--source`` to a checkout of ``BoundaryLogic/privaci-commercial``.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_DIR = _ENGINE_ROOT / "docs" / "commercial"
_MANIFEST_NAME = "docs/publishable.txt"

_GITHUB_ENGINE_BLOB = re.compile(
    r"https://github\.com/BoundaryLogic/privaci/blob/main/docs/([^)\s#]+)([#][^)\s]*)?"
)

_NAV_TITLES: dict[str, str] = {
    "quickstart.md": "Quickstart",
    "licensing-and-entitlement.md": "Licensing & entitlement",
    "signed-reports.md": "Signed reports",
    "drift-detection.md": "Drift detection",
    "subsetting.md": "Data subsetting",
    "jsonb-masking.md": "JSONB path masking",
    "preview-and-ci.md": "Preview & CI gates",
    "compliance-evidence-mapping.md": "Compliance evidence",
    "troubleshooting.md": "Troubleshooting",
}

_INTERNAL_LINK = re.compile(
    r"\[([^\]]+)\]\((?:\.\./)?(?:adr|spikes|strategy|openspec|runbooks)/[^)]+\)"
)
_ENV_EXAMPLE_LINK = re.compile(
    r"\[`?\.env\.example`?\]\(\.\./\.env\.example\)",
    re.I,
)
_BROKEN_ANCHOR = re.compile(r"#field--framework-mapping")


def _rewrite_engine_links(content: str) -> str:
    """Map GitHub blob links to docs.boundarylogic.io paths."""

    def _repl(match: re.Match[str]) -> str:
        rel = match.group(1).removesuffix(".md")
        anchor = match.group(2) or ""
        return f"https://docs.boundarylogic.io/{rel}/{anchor}"

    return _GITHUB_ENGINE_BLOB.sub(_repl, content)


def _sanitize_internal_links(content: str) -> str:
    """Drop or replace links to paths that are not published on docs.boundarylogic.io."""
    content = _INTERNAL_LINK.sub(r"\1", content)
    content = _ENV_EXAMPLE_LINK.sub(
        "[Deployment environment variables](https://docs.boundarylogic.io/deployment/)",
        content,
    )
    return _BROKEN_ANCHOR.sub("#field-framework-mapping", content)


def _prepare_content(content: str) -> str:
    return _sanitize_internal_links(_rewrite_engine_links(content))


def _load_manifest(commercial_root: Path) -> list[Path]:
    manifest = commercial_root / _MANIFEST_NAME
    if not manifest.is_file():
        msg = f"Missing manifest: {manifest}"
        raise FileNotFoundError(msg)
    paths: list[Path] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        source = commercial_root / stripped
        if not source.is_file():
            msg = f"Publishable entry not found: {source}"
            raise FileNotFoundError(msg)
        paths.append(source)
    if not paths:
        msg = f"No publishable paths in {manifest}"
        raise ValueError(msg)
    return paths


def _sync_file(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    rewritten = _prepare_content(source.read_text(encoding="utf-8"))
    dest.write_text(rewritten, encoding="utf-8")


def _write_index(dest_dir: Path, synced: list[str]) -> None:
    lines = [
        "# PrivaCI Commercial",
        "",
        "Customer-facing documentation for the **PrivaCI Commercial** layer",
        "(AWS Marketplace container image).",
        "",
        "> **Synced copy.** Edit sources in the private",
        "> [`privaci-commercial`](https://github.com/BoundaryLogic/privaci-commercial)",
        "> repository (`docs/publishable.txt`). This tree is updated automatically",
        "> when publishable docs change on the commercial `main` branch.",
        "",
        f"_Last synced: {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Guides",
        "",
    ]
    for name in synced:
        title = _NAV_TITLES.get(
            name, name.removesuffix(".md").replace("-", " ").title()
        )
        lines.append(f"- [{title}]({name})")
    lines.append("")
    (dest_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def sync_commercial_docs(*, commercial_root: Path) -> list[str]:
    """Copy publishable commercial docs; return basenames written."""
    sources = _load_manifest(commercial_root)
    synced: list[str] = []
    for source in sources:
        basename = source.name
        _sync_file(source, _OUTPUT_DIR / basename)
        synced.append(basename)
    _write_index(_OUTPUT_DIR, synced)
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to a privaci-commercial clone (contains docs/publishable.txt).",
    )
    args = parser.parse_args()
    commercial_root = args.source.resolve()
    if not commercial_root.is_dir():
        print(f"ERROR: not a directory: {commercial_root}", file=sys.stderr)
        return 1
    try:
        synced = sync_commercial_docs(commercial_root=commercial_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Synced {len(synced)} files to {_OUTPUT_DIR.relative_to(_ENGINE_ROOT)}/")
    for name in synced:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
