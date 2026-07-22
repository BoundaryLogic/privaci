"""Shared helpers for PrivaCI CI gate scripts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ISSUE_KEYED_ENTRY_RE = re.compile(
    r"^([^:#\s]+(?::[^\s#]+)?)\s+#\s*issue\s+#(\d+)\s*$",
    re.IGNORECASE,
)


def ensure_scripts_on_path() -> Path:
    """Insert ``scripts/`` on ``sys.path``; return the scripts directory."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return scripts_dir


def iter_privaci_py_files(repo_root: Path) -> list[Path]:
    """Return ``src/privaci/**/*.py`` paths excluding spikes."""
    base = repo_root / "src" / "privaci"
    if not base.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(base.rglob("*.py")):
        if "spikes" in path.parts:
            continue
        paths.append(path)
    return paths


def load_issue_keyed_entries(path: Path) -> dict[str, int]:
    """Load ``path[:key] # issue #N`` lines into ``{entry: issue_number}``."""
    entries: dict[str, int] = {}
    if not path.is_file():
        return entries
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ISSUE_KEYED_ENTRY_RE.match(line)
        if not match:
            msg = (
                "invalid allowlist/waiver entry "
                f"(expected path[:lineno|symbol] # issue #N): {raw}"
            )
            raise ValueError(msg)
        entries[match.group(1)] = int(match.group(2))
    return entries


def report_errors(title: str, errors: list[str]) -> int:
    """Print errors to stderr; return 1 if any, else 0."""
    if not errors:
        return 0
    print(f"ERROR: {title}", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    return 1
