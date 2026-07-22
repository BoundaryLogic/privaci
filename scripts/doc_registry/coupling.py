"""Code-to-docs diff coupling checks."""

from __future__ import annotations

from doc_registry.globs import path_matches_glob
from doc_registry.models import ISSUE_WAIVER_PATTERN, Registry, RegistryEntry


def entry_has_waiver(entry: RegistryEntry) -> bool:
    """Return True when coupling is suppressed for an entry."""
    return bool(entry.waiver and ISSUE_WAIVER_PATTERN.search(entry.waiver))


def check_coupling(
    registry: Registry,
    changed_files: frozenset[str],
    changelog_path: str = "CHANGELOG.md",
) -> list[str]:
    """Fail when code paths change without bound docs (and CHANGELOG when required)."""
    errors: list[str] = []
    for entry in registry.entries:
        if entry_has_waiver(entry):
            continue
        code_touched = any(
            path_matches_glob(path, pattern)
            for path in changed_files
            for pattern in entry.code
        )
        if not code_touched or not entry.docs:
            continue
        docs_touched = any(
            path_matches_glob(path, pattern)
            for path in changed_files
            for pattern in entry.docs
        )
        if not docs_touched:
            errors.append(
                f"entry {entry.id!r}: code changed without updating bound docs "
                f"({', '.join(entry.docs)})"
            )
        if entry.changelog == "required" and changelog_path not in changed_files:
            errors.append(
                f"entry {entry.id!r}: changelog: required but {changelog_path} not updated"
            )
    return errors
