#!/usr/bin/env python3
"""Guard public-repo language per ADR-0007 (plugin contracts, not commercial features).

The public engine implements ``privaci.contracts`` plugin lifecycle hooks. Commit
messages, release notes, and engine implementation comments must not frame that
work as "commercial" features — billing and entitlement live in ``privaci-commercial``.

Run:
  python scripts/check_public_repo_language.py              # scan watched paths
  python scripts/check_public_repo_language.py --commit-msg-file .git/COMMIT_EDITMSG
  python scripts/check_public_repo_language.py --git-log 50 # recent commit subjects
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paths where "commercial feature" framing is forbidden (not ADR/split docs).
_WATCHED_PATHS: tuple[Path, ...] = (
    ROOT / "src" / "privaci" / "pipeline",
    ROOT / ".github" / "release-notes",
    ROOT / "CHANGELOG.md",
)

# Forbidden in commit subjects/bodies and in watched implementation/release text.
_BANNED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bcommercial\s+(hook|hooks|entitlement|meter|metering)\b", re.I),
        "Use plugin contract / UsageMeter lifecycle wording instead.",
    ),
    (
        re.compile(r"\bcommercial\s+UsageMeter\b", re.I),
        "Say UsageMeter plugin contract, not commercial UsageMeter.",
    ),
    (
        re.compile(r"\bcommercial\s+contract\s+hook", re.I),
        "Say plugin contract hook(s), not commercial contract hook(s).",
    ),
    (
        re.compile(r"\bfor\s+commercial\s+entitlement\b", re.I),
        "Entitlement enforcement is private; public commits describe contract hooks.",
    ),
)


def _find_violations(text: str, *, label: str) -> list[str]:
    hits: list[str] = []
    for pattern, hint in _BANNED_PATTERNS:
        for match in pattern.finditer(text):
            hits.append(f"{label}: matched {match.group()!r} — {hint}")
    return hits


def scan_paths() -> list[str]:
    """Scan watched files for banned public-repo language."""
    violations: list[str] = []
    for base in _WATCHED_PATHS:
        if base.is_file():
            text = base.read_text(encoding="utf-8")
            violations.extend(_find_violations(text, label=str(base.relative_to(ROOT))))
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".md"}:
                continue
            text = path.read_text(encoding="utf-8")
            violations.extend(
                _find_violations(text, label=str(path.relative_to(ROOT)))
            )
    return violations


def scan_commit_message(message: str) -> list[str]:
    """Scan a commit message for banned public-repo language."""
    return _find_violations(message, label="commit message")


def scan_git_log(count: int) -> list[str]:
    """Scan recent commit subjects and bodies on the current branch."""
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
        for hit in _find_violations(body, label=f"commit #{index}"):
            violations.append(hit)
    return violations


def main() -> int:
    """Return 0 when no banned language is found."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit-msg-file",
        type=Path,
        help="Path to the commit message file (pre-commit commit-msg hook).",
    )
    parser.add_argument(
        "--git-log",
        type=int,
        metavar="N",
        help="Also scan the last N commit messages (CI guard).",
    )
    args = parser.parse_args()

    violations: list[str] = []
    if args.commit_msg_file is not None:
        message = args.commit_msg_file.read_text(encoding="utf-8")
        violations.extend(scan_commit_message(message))
    else:
        violations.extend(scan_paths())

    if args.git_log is not None:
        violations.extend(scan_git_log(args.git_log))

    if not violations:
        return 0

    sys.stderr.write(
        "ERROR: Public repo language guard failed (ADR-0007).\n"
        "The public engine implements plugin contracts; do not label engine work "
        "as commercial features in commits or release artifacts.\n"
        "See .cursor/rules/public-repo-language.mdc\n\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
