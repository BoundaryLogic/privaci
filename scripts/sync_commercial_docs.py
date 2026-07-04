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
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_DIR = _ENGINE_ROOT / "docs" / "commercial"
_MANIFEST_NAME = "docs/publishable.txt"
_QUICK_LAUNCH_REL = Path("infra/marketplace-quick-launch/quick-launch.yaml")
_QUICK_LAUNCH_URL = "https://docs.boundarylogic.io/commercial/assets/quick-launch.yaml"

_GITHUB_ENGINE_BLOB = re.compile(
    r"https://github\.com/BoundaryLogic/privaci/blob/main/docs/([^)\s#]+)([#][^)\s]*)?"
)

_PAGE_META: dict[str, tuple[str, str]] = {
    "quickstart.md": (
        "Commercial quickstart",
        "Run the AWS Marketplace PrivaCI Commercial image in your VPC and "
        "produce a signed compliance report.",
    ),
    "licensing-and-entitlement.md": (
        "Licensing & entitlement",
        "Marketplace subscription, tier limits, JWT offline licenses, and "
        "usage metering for PrivaCI Commercial.",
    ),
    "signed-reports.md": (
        "Signed reports",
        "Generate, sign, verify, and archive tamper-evident JSON compliance "
        "reports after a mask run.",
    ),
    "drift-detection.md": (
        "Drift detection",
        "Detect production schema drift vs stored snapshots and block stale "
        "staging refreshes in CI.",
    ),
    "subsetting.md": (
        "Data subsetting",
        "Subset production tables with filters while preserving referential "
        "integrity in masked output.",
    ),
    "jsonb-masking.md": (
        "JSONB path masking",
        "Mask nested JSONB fields by path without flattening documents.",
    ),
    "preview-and-ci.md": (
        "Preview & CI gates",
        "Run privaci preview in CI to diff masking policy before production jobs.",
    ),
    "compliance-evidence-mapping.md": (
        "Compliance evidence",
        "Map PrivaCI run artifacts to GDPR, HIPAA, SOC 2, and ISO 27001 evidence.",
    ),
    "troubleshooting.md": (
        "Commercial troubleshooting",
        "Commercial exit codes 5 and 6 — license, entitlement, and drift failures.",
    ),
}

_DEV_LICENSE_LINE = re.compile(r"^.*PRIVACI_COMMERCIAL_DEV_LICENSE.*\n?", re.MULTILINE)

_INTERNAL_LINK = re.compile(
    r"\[([^\]]+)\]\((?:\.\./)?(?:adr|spikes|strategy|openspec|runbooks|marketplace)/[^)]+\)"
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


def _strip_internal_only_content(content: str) -> str:
    """Remove contributor-only env vars and FAQ blocks from customer-facing copy."""
    content = _DEV_LICENSE_LINE.sub("", content)
    content = re.sub(
        r"\*\*Is `PRIVACI_COMMERCIAL_DEV_LICENSE` for customers\?\*\*\s*\n[^\n]+\n[^\n]+\n\n",
        "",
        content,
    )
    return content


def _ensure_frontmatter(content: str, *, title: str, description: str) -> str:
    """Inject or replace YAML front matter for page title and meta description."""
    esc_title = title.replace('"', '\\"')
    esc_desc = description.replace('"', '\\"')
    block = f'---\ntitle: "{esc_title}"\ndescription: "{esc_desc}"\n---\n\n'
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            body = content[end + 4 :].lstrip("\n")
            return block + body
    return block + content


def _prepare_content(content: str, *, basename: str) -> str:
    content = _strip_internal_only_content(content)
    content = _sanitize_internal_links(_rewrite_engine_links(content))
    meta = _PAGE_META.get(basename)
    if meta:
        content = _ensure_frontmatter(content, title=meta[0], description=meta[1])
    return content


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
    rewritten = _prepare_content(source.read_text(encoding="utf-8"), basename=dest.name)
    dest.write_text(rewritten, encoding="utf-8")


def _sync_quick_launch_template(commercial_root: Path) -> Path:
    """Copy the Marketplace quick-launch CloudFormation template as a static asset."""
    source = commercial_root / _QUICK_LAUNCH_REL
    if not source.is_file():
        msg = f"Quick launch template not found: {source}"
        raise FileNotFoundError(msg)
    dest = _OUTPUT_DIR / "assets" / source.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return dest


def _write_index(dest_dir: Path, synced: list[str]) -> None:
    lines = [
        "---",
        'title: "Commercial overview"',
        (
            'description: "PrivaCI Commercial AWS Marketplace docs — licensing, signed '
            + 'reports, drift detection, subsetting, and compliance evidence."'
        ),
        "---",
        "",
        "# PrivaCI Commercial",
        "",
        "Documentation for the **PrivaCI Commercial** AWS Marketplace container",
        "image: licensing, signed compliance reports, drift detection, data",
        "subsetting, JSONB masking, CI preview gates, and GRC evidence exports.",
        "",
        "For the open engine (install, configuration, CLI), see the",
        "[Getting started](../index.md) and [Operating](../cli-reference.md) tabs.",
        "",
        "## Guides",
        "",
    ]
    for name in synced:
        meta = _PAGE_META.get(name)
        title = meta[0] if meta else name.removesuffix(".md").replace("-", " ").title()
        lines.append(f"- [{title}]({name})")
    lines.append("")
    (dest_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def sync_commercial_docs(*, commercial_root: Path) -> tuple[list[str], Path]:
    """Copy publishable commercial docs and quick-launch CFN; return doc basenames."""
    sources = _load_manifest(commercial_root)
    synced: list[str] = []
    for source in sources:
        basename = source.name
        _sync_file(source, _OUTPUT_DIR / basename)
        synced.append(basename)
    _write_index(_OUTPUT_DIR, synced)
    quick_launch = _sync_quick_launch_template(commercial_root)
    return synced, quick_launch


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
        synced, quick_launch = sync_commercial_docs(commercial_root=commercial_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Synced {len(synced)} files to {_OUTPUT_DIR.relative_to(_ENGINE_ROOT)}/")
    for name in synced:
        print(f"  - {name}")
    rel_asset = quick_launch.relative_to(_ENGINE_ROOT)
    print(f"Synced quick-launch template to {rel_asset} ({_QUICK_LAUNCH_URL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
