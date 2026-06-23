#!/usr/bin/env python3
"""Guard public-repo language per ADR-0007 (plugin contracts, not commercial features).

The public engine implements ``privaci.contracts`` plugin hooks. Product tiers,
Marketplace pricing, and "commercial feature" framing belong in ``privaci-commercial``.

Run:
  python scripts/check_public_repo_language.py --staged   # pre-commit (added lines)
  python scripts/check_public_repo_language.py --full     # CI / before push
  python scripts/check_public_repo_language.py --commit-msg-file PATH
  python scripts/check_public_repo_language.py --git-log 30
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paths skipped entirely (explain the public/private split or define the guard).
_ALLOWLIST_EXACT: frozenset[str] = frozenset(
    {
        "scripts/check_public_repo_language.py",
        ".cursor/rules/public-repo-language.mdc",
        "docs/adr/0007-public-commercial-split.md",
        "docs/adr/0003-billing-dimension-source-dbs.md",
        "docs/adr/0001-elv2-license.md",
        "docs/extending-privaci.md",
    }
)

_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "docs/adr/",
    "docs/spikes/",
    "openspec/changes/archive/",
    "openspec/changes/add-state-schema-abstraction/specs/commercial-tier-contract/",
    "openspec/changes/add-artifact-object-output/specs/commercial-tier-contract/",
)

# Operator UX: exit codes, install hints (ADR-0007 allowed).
_OPERATOR_UX_PREFIXES: tuple[str, ...] = (
    "src/privaci/cli/",
    "src/privaci/errors.py",
    "src/privaci/config/loader.py",
    "src/privaci/contracts/fallbacks.py",
    "src/privaci/mask/column_masker.py",
    "src/privaci/config/actions.py",
    "docs/error-codes.md",
    "docs/generated/errors/",
    "docs/cli-reference.md",
    "docs/generated/cli-reference.md",
)

_SCAN_ROOTS: tuple[Path, ...] = (
    ROOT / "src" / "privaci",
    ROOT / "docs" / "object-output.md",
    ROOT / "docs" / "configuration.md",
    ROOT / "docs" / "cli-reference.md",
    ROOT / ".github" / "release-notes",
)

_TEXT_SUFFIXES = frozenset({".py", ".md", ".yaml", ".yml", ".toml"})

# Always forbidden in non-allowlisted paths (prose / docs / framing).
_BANNED_ALWAYS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bcommercial\s+(hook|hooks|entitlement|meter|metering)\b", re.I),
        "Use plugin contract / UsageMeter lifecycle wording.",
    ),
    (
        re.compile(r"\bcommercial\s+UsageMeter\b", re.I),
        "Say UsageMeter plugin contract.",
    ),
    (
        re.compile(r"\bcommercial\s+contract\s+hook", re.I),
        "Say plugin contract hook(s).",
    ),
    (
        re.compile(r"\bcommercial\s+plugin\b", re.I),
        "Name the hook (object_writer) or say plugin package.",
    ),
    (
        re.compile(r"\bGrowth\+?\b"),
        "Do not name product tiers; say license-gated.",
    ),
    (
        re.compile(r"\bGrowth tier\b", re.I),
        "Do not name product tiers; say license-gated.",
    ),
    (
        re.compile(r"\bStarter tier\b", re.I),
        "Do not name product tiers; say license-gated.",
    ),
    (
        re.compile(r"\bBusiness\+?\b"),
        "Do not name product tiers; say license-gated.",
    ),
    (
        re.compile(r"\bEnterprise tier\b", re.I),
        "Do not name product tiers; say license-gated.",
    ),
    (
        re.compile(r"\ball tiers\b", re.I),
        "Describe community fallback vs plugin-installed behaviour.",
    ),
    (
        re.compile(r"\bAWS Marketplace\b"),
        "Marketplace is private-repo language; use official container image.",
    ),
    (
        re.compile(r"\bMarketplace subscription\b", re.I),
        "Subscription/tiering is private-repo language.",
    ),
    (
        re.compile(r"\bcommercial S3\b", re.I),
        "Say object_writer plugin or S3-capable plugin.",
    ),
)

# Forbidden outside operator UX paths (install hints / exit 5–6 are OK there).
_BANNED_OUTSIDE_OPERATOR_UX: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bcommercial layer\b", re.I),
        "Allowed only in CLI/errors/install hints; use plugin package elsewhere.",
    ),
    (
        re.compile(r"\bprivaci-commercial\b", re.I),
        "Allowed only in install hints; say plugin package elsewhere.",
    ),
    (
        re.compile(r"\bMarketplace\b"),
        "Allowed only in ADR/spikes; omit from operator guides and code comments.",
    ),
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _is_allowlisted(rel: str) -> bool:
    if rel in _ALLOWLIST_EXACT:
        return True
    return any(rel.startswith(prefix) for prefix in _ALLOWLIST_PREFIXES)


def _is_operator_ux(rel: str) -> bool:
    return any(rel.startswith(prefix) or rel == prefix.rstrip("/") for prefix in _OPERATOR_UX_PREFIXES)


def _patterns_for(rel: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    patterns = _BANNED_ALWAYS
    if not _is_operator_ux(rel):
        patterns = patterns + _BANNED_OUTSIDE_OPERATOR_UX
    return patterns


def _find_violations(text: str, *, label: str, rel: str) -> list[str]:
    if _is_allowlisted(rel):
        return []
    hits: list[str] = []
    for pattern, hint in _patterns_for(rel):
        for match in pattern.finditer(text):
            hits.append(f"{label}: matched {match.group()!r} — {hint}")
    return hits


def scan_staged() -> list[str]:
    """Scan added lines in the git index (pre-commit gate)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    violations: list[str] = []
    current_rel = ""
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_rel = line.removeprefix("+++ b/").strip()
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not current_rel or _is_allowlisted(current_rel):
            continue
        added = line[1:]
        violations.extend(
            _find_violations(added, label=f"{current_rel} (staged +)", rel=current_rel)
        )
    return violations


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for base in _SCAN_ROOTS:
        if base.is_file():
            files.append(base)
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in _TEXT_SUFFIXES:
                files.append(path)
    return files


def scan_full() -> list[str]:
    """Scan tracked public surfaces (CI gate)."""
    violations: list[str] = []
    for path in _iter_scan_files():
        rel = _rel(path)
        if _is_allowlisted(rel):
            continue
        text = path.read_text(encoding="utf-8")
        violations.extend(_find_violations(text, label=rel, rel=rel))
    return violations


def scan_commit_message(message: str) -> list[str]:
    """Commit messages are never allowlisted."""
    violations: list[str] = []
    for pattern, hint in _BANNED_ALWAYS + _BANNED_OUTSIDE_OPERATOR_UX:
        for match in pattern.finditer(message):
            violations.append(f"commit message: matched {match.group()!r} — {hint}")
    return violations


def scan_git_log(count: int) -> list[str]:
    """Scan recent commit messages (CI gate)."""
    result = subprocess.run(
        ["git", "log", f"-{count}", "--format=%B---END---"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    violations: list[str] = []
    for index, block in enumerate(result.stdout.split("---END---"), start=1):
        body = block.strip()
        if not body:
            continue
        for hit in scan_commit_message(body):
            violations.append(hit.replace("commit message:", f"commit #{index}:"))
    return violations


def _report(violations: list[str]) -> int:
    if not violations:
        return 0
    sys.stderr.write(
        "ERROR: Public repo language guard failed (ADR-0007).\n"
        "Scrub product tiers, Marketplace, and commercial *feature* framing before "
        "commit. Plugin contracts and operator install hints are fine.\n"
        "See .cursor/rules/public-repo-language.mdc\n\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n"
    )
    return 1


def main() -> int:
    """Return 0 when no banned language is found."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--staged",
        action="store_true",
        help="Scan added lines in the git index (default for pre-commit).",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="Scan src/, docs/, release notes, CHANGELOG (CI).",
    )
    parser.add_argument(
        "--commit-msg-file",
        type=Path,
        help="Scan a commit message file (commit-msg hook).",
    )
    parser.add_argument(
        "--git-log",
        type=int,
        metavar="N",
        help="Also scan the last N commit messages.",
    )
    args = parser.parse_args()

    violations: list[str] = []
    if args.commit_msg_file is not None:
        message = args.commit_msg_file.read_text(encoding="utf-8")
        violations.extend(scan_commit_message(message))
    elif args.full:
        violations.extend(scan_full())
    elif args.staged:
        violations.extend(scan_staged())
    else:
        violations.extend(scan_staged())
        violations.extend(scan_full())

    if args.git_log is not None:
        violations.extend(scan_git_log(args.git_log))

    return _report(violations)


if __name__ == "__main__":
    raise SystemExit(main())
