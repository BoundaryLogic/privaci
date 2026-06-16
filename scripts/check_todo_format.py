#!/usr/bin/env python3
"""Pre-commit guard: every added TODO must name an author and an issue number.

Replaces a bash+grep hook whose ``grep -E`` behavior differed between GNU and
BSD (macOS) userlands. Scans the staged diff for added Python lines that open a
TODO marker and rejects any that do not match the form
``# TODO(initials): ... #123``.

Run: ``python scripts/check_todo_format.py``
"""

from __future__ import annotations

import re
import subprocess
import sys

# Assembled from parts so this guard never flags its own definition line.
_TODO_MARKER = "# TODO" + "("
# A well-formed marker names the author's initials and links an issue number,
# e.g. ``# TODO(jd): replace with async version — see #42``.
_VALID_TODO = re.compile(r"# TODO\([a-z]+\):.*#[0-9]+")


def find_offending_todos(diff_text: str) -> list[str]:
    """Return added diff lines with a malformed TODO marker.

    Args:
        diff_text: Unified ``git diff`` output (``-U0`` is sufficient).

    Returns:
        The offending added source lines (without the leading ``+``), in order.
    """
    offenders: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        if _TODO_MARKER in added and not _VALID_TODO.search(added):
            offenders.append(added.strip())
    return offenders


def _staged_python_diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", "*.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    """Return 0 when every added TODO names an author and issue number."""
    offenders = find_offending_todos(_staged_python_diff())
    if not offenders:
        return 0
    sys.stderr.write(
        "ERROR: TODO comments must include author initials and an issue number,\n"
        "e.g. # TODO(jd): replace with async version — see #42\n"
        "Offending line(s):\n" + "\n".join(f"  - {line}" for line in offenders) + "\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
