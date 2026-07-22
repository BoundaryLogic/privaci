"""Registry shape validation and package coverage checks."""

from __future__ import annotations

from pathlib import Path

from doc_registry.globs import path_matches_glob, unsupported_glob_reason
from doc_registry.models import (
    ISSUE_WAIVER_PATTERN,
    PACKAGES_ROOT,
    REPO_ROOT,
    Registry,
    RegistryEntry,
)


def _entry_structure_errors(
    entry: RegistryEntry,
    *,
    seen_ids: set[str],
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    if entry.id in seen_ids:
        errors.append(f"duplicate registry entry id: {entry.id!r}")
    seen_ids.add(entry.id)
    if not entry.code:
        errors.append(f"entry {entry.id!r}: code globs must not be empty")
    if entry.waiver and not ISSUE_WAIVER_PATTERN.search(entry.waiver):
        errors.append(
            f"entry {entry.id!r}: waiver must reference an issue (e.g. issue #42)"
        )
    for pattern in (*entry.code, *entry.docs):
        reason = unsupported_glob_reason(pattern)
        if reason is not None:
            errors.append(f"entry {entry.id!r}: {reason}")
    for doc_path in entry.docs:
        if "**" in doc_path:
            prefix = doc_path.split("**", maxsplit=1)[0].rstrip("/")
            target = repo_root / prefix if prefix else repo_root
            if not target.exists():
                errors.append(f"entry {entry.id!r}: docs prefix missing: {doc_path}")
        elif not (repo_root / doc_path).is_file():
            errors.append(f"entry {entry.id!r}: docs path missing: {doc_path}")
    return errors


def validate_structure(registry: Registry, repo_root: Path = REPO_ROOT) -> list[str]:
    """Validate registry shape, meta excludes, and bound doc paths."""
    errors: list[str] = []
    if "spikes" not in registry.exclude_packages:
        errors.append("meta.exclude_packages MUST include 'spikes'")
    seen_ids: set[str] = set()
    for entry in registry.entries:
        errors.extend(
            _entry_structure_errors(entry, seen_ids=seen_ids, repo_root=repo_root)
        )
    return errors


def list_top_level_packages(
    packages_root: Path = PACKAGES_ROOT,
    exclude: frozenset[str] | None = None,
) -> set[str]:
    """Return top-level package directory names under ``src/privaci/``."""
    excluded = exclude or frozenset()
    names: set[str] = set()
    if not packages_root.is_dir():
        return names
    for child in packages_root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.name in excluded:
            continue
        names.add(child.name)
    return names


def pattern_covers_package(pattern: str, package: str) -> bool:
    """Return True when a registry code glob covers a top-level package."""
    probes = (
        f"src/privaci/{package}/__init__.py",
        f"src/privaci/{package}/module.py",
    )
    return any(path_matches_glob(probe, pattern) for probe in probes)


def check_package_coverage(
    registry: Registry,
    packages_root: Path = PACKAGES_ROOT,
) -> list[str]:
    """Fail when a non-excluded package lacks a registry row."""
    errors: list[str] = []
    packages = list_top_level_packages(packages_root, registry.exclude_packages)
    for package in sorted(packages):
        covered = False
        for entry in registry.entries:
            if any(pattern_covers_package(pattern, package) for pattern in entry.code):
                covered = True
                break
        if not covered:
            errors.append(
                f"package {package!r} is not bound in docs/registry.yaml "
                f"(add an entry or meta exclude with waiver)"
            )
    return errors
