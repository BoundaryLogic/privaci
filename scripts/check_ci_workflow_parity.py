#!/usr/bin/env python3
"""Fail closed when GitHub workflows drift from local CI tool choices.

Catches the class of PR-only failures where Actions use a different binary or
config than ``scripts/ci-local.sh`` (e.g. licensed gitleaks-action vs OSS CLI,
advanced CodeQL vs org default setup).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ci_gate_common import report_errors

_GITLEAKS_ACTION_RE = re.compile(r"gitleaks/gitleaks-action@")
_GITLEAKS_VER_ASSIGN_RE = re.compile(r'\bver="(\d+\.\d+\.\d+)"')
_GITLEAKS_TARBALL_RE = re.compile(
    r"gitleaks_(?:\$\{ver\}|(\d+\.\d+\.\d+))_linux_x64\.tar\.gz"
)
_PRECOMMIT_GITLEAKS_RE = re.compile(
    r"repo:\s*https://github\.com/gitleaks/gitleaks\s*\n\s*rev:\s*v(\d+\.\d+\.\d+)",
    re.MULTILINE,
)
_SEMGREP_IMAGE_RE = re.compile(r"image:\s*semgrep/semgrep:([\w.\-]+)")
_SEMGREP_REQUIRED_FLAGS = (
    "--config=.semgrep.yml",
    "--config=auto",
    "--error",
    "--severity=ERROR",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def collect_parity_findings(repo_root: Path) -> list[str]:
    """Return workflow/pre-commit drift findings for ``repo_root``."""
    findings: list[str] = []
    workflows = repo_root / ".github" / "workflows"
    ci_yml = _read(workflows / "ci.yml")
    semgrep_yml = _read(workflows / "semgrep.yml")
    pre_commit = _read(repo_root / ".pre-commit-config.yaml")

    findings.extend(_gitleaks_findings(ci_yml, pre_commit, workflows))
    findings.extend(_codeql_findings(workflows))
    findings.extend(_semgrep_findings(semgrep_yml))
    return findings


def _gitleaks_cli_version(ci_yml: str) -> str | None:
    """Return pinned gitleaks CLI version from ci.yml, if present."""
    if not _GITLEAKS_TARBALL_RE.search(ci_yml):
        return None
    assigned = _GITLEAKS_VER_ASSIGN_RE.search(ci_yml)
    if assigned:
        return assigned.group(1)
    literal = _GITLEAKS_TARBALL_RE.search(ci_yml)
    if literal and literal.group(1):
        return literal.group(1)
    return None


def _gitleaks_findings(ci_yml: str, pre_commit: str, workflows: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if _GITLEAKS_ACTION_RE.search(text):
            findings.append(
                f"{path.name}: uses gitleaks-action (org license required); "
                "use the gitleaks OSS CLI like ci-local / pre-commit"
            )
    cli_ver = _gitleaks_cli_version(ci_yml)
    hook_match = _PRECOMMIT_GITLEAKS_RE.search(pre_commit)
    if ci_yml and cli_ver is None:
        findings.append(
            "ci.yml: expected pinned gitleaks OSS CLI download "
            "(gitleaks_<ver>_linux_x64.tar.gz)"
        )
    if cli_ver and hook_match and cli_ver != hook_match.group(1):
        findings.append(
            "gitleaks version drift: ci.yml installs "
            f"v{cli_ver} but pre-commit pins "
            f"v{hook_match.group(1)}"
        )
    return findings


def _codeql_findings(workflows: Path) -> list[str]:
    codeql = workflows / "codeql.yml"
    if codeql.is_file():
        return [
            "codeql.yml present: advanced CodeQL conflicts with GitHub "
            "default setup SARIF upload — remove the workflow and rely on "
            "default setup (see docs/ci-gates.md)"
        ]
    return []


def _semgrep_findings(semgrep_yml: str) -> list[str]:
    if not semgrep_yml:
        return ["semgrep.yml missing — PR Semgrep job required"]
    findings: list[str] = []
    if not _SEMGREP_IMAGE_RE.search(semgrep_yml):
        findings.append("semgrep.yml: expected pinned semgrep/semgrep image")
    collapsed = " ".join(semgrep_yml.split())
    for flag in _SEMGREP_REQUIRED_FLAGS:
        if flag not in collapsed:
            findings.append(f"semgrep.yml: missing required flag {flag}")
    return findings


def main(argv: list[str] | None = None) -> int:
    """CLI entry for workflow / local tool parity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    args = parser.parse_args(argv)
    repo = args.repo_root or Path(__file__).resolve().parents[1]
    return report_errors(
        "CI workflow parity check failed.",
        collect_parity_findings(repo.resolve()),
    )


if __name__ == "__main__":
    sys.exit(main())
