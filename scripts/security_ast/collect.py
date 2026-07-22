"""Scan engine packages and collect security AST findings."""

from __future__ import annotations

import ast
from pathlib import Path

from ci_gate_common import iter_privaci_py_files, load_issue_keyed_entries
from security_ast.constants import SCAN_PACKAGES
from security_ast.findings import Finding
from security_ast.helpers import package_for_path
from security_ast.visitor import SecurityVisitor, package_uses_http

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "security_ast_allowlist.txt"


def load_allowlist(path: Path | None = None) -> set[str]:
    """Load ``path:lineno`` or ``path:symbol`` allowlist entries."""
    allowlist_path = path if path is not None else ALLOWLIST_PATH
    return set(load_issue_keyed_entries(allowlist_path))


def _scan_one_path(
    path: Path,
    *,
    repo_root: Path,
    allowlist: set[str],
) -> list[Finding]:
    """Parse and visit one engine file; return findings for that path."""
    rel = path.relative_to(repo_root).as_posix()
    package = package_for_path(rel)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except SyntaxError as exc:
        return [
            Finding(
                rel_path=rel,
                line=exc.lineno or 1,
                rule="syntax-error",
                detail=str(exc.msg),
            )
        ]
    except OSError as exc:
        return [
            Finding(
                rel_path=rel,
                line=1,
                rule="unreadable-file",
                detail=f"cannot read file: {exc}",
            )
        ]
    visitor = SecurityVisitor(
        rel_path=rel,
        allowlist=allowlist,
        check_http=package_uses_http(package),
        full_rules=package in SCAN_PACKAGES,
    )
    visitor.visit(tree)
    return visitor.findings


def collect_findings(repo_root: Path = REPO_ROOT) -> list[Finding]:
    """Scan engine packages once; apply full rules only on SCAN_PACKAGES."""
    base = repo_root / "src" / "privaci"
    if not base.is_dir() or not any(base.rglob("*.py")):
        return [
            Finding(
                rel_path="src/privaci",
                line=1,
                rule="empty-scan",
                detail="no Python files found under src/privaci",
            )
        ]
    paths = iter_privaci_py_files(repo_root)
    allowlist = load_allowlist(repo_root / "scripts" / "security_ast_allowlist.txt")
    findings: list[Finding] = []
    for path in paths:
        findings.extend(_scan_one_path(path, repo_root=repo_root, allowlist=allowlist))
    return findings
