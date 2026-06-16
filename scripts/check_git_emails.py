#!/usr/bin/env python3
"""CI guard: reject personal emails in git author/committer fields and messages.

Scans every ref reachable from HEAD. Fails when any author or committer email
is not a GitHub noreply address and not an allowed org domain. Run before a
public launch; see ``docs/runbooks/git-history-privacy.md``.

Run: ``python scripts/check_git_emails.py``
"""

from __future__ import annotations

import re
import subprocess
import sys

_ALLOWED_SUFFIXES = (
    "@users.noreply.github.com",
    "@noreply.github.com",
)
_ALLOWED_EXACT = frozenset({"noreply@github.com"})
_ALLOWED_DOMAINS = ("@boundarylogic.io",)
_MESSAGE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _is_allowed(email: str) -> bool:
    lowered = email.lower()
    if lowered in _ALLOWED_EXACT:
        return True
    if any(lowered.endswith(suffix) for suffix in _ALLOWED_SUFFIXES):
        return True
    return any(lowered.endswith(domain) for domain in _ALLOWED_DOMAINS)


def _collect_author_emails() -> set[str]:
    lines = _git_lines("log", "--all", "--format=%ae %ce")
    emails: set[str] = set()
    for line in lines:
        for part in line.split():
            emails.add(part.strip())
    return emails


def _collect_message_emails() -> set[str]:
    bodies = _git_lines("log", "--all", "--format=%B")
    emails: set[str] = set()
    for body in bodies:
        emails.update(_MESSAGE_EMAIL.findall(body))
    return emails


def main() -> int:
    """Return 0 when no disallowed emails are found."""
    offenders = sorted(
        email
        for email in (_collect_author_emails() | _collect_message_emails())
        if not _is_allowed(email)
    )
    if not offenders:
        return 0
    sys.stderr.write(
        "ERROR: disallowed email address(es) found in git history:\n"
        + "\n".join(f"  - {email}" for email in offenders)
        + "\nSee docs/runbooks/git-history-privacy.md for remediation.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
