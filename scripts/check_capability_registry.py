#!/usr/bin/env python3
"""Pre-commit guard: capability registry stays valid and new tests are registered.

Validates:

- Every ``Capability.test_paths`` entry exists on disk.
- Capability ids follow ``public-*`` / ``commercial-*`` naming.
- Newly added unit test files (staged) appear in the registry unless
  ``scripts/capability_test/registry.py`` is also staged.

Run: ``python scripts/check_capability_registry.py``
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.capability_test.registry import CAPABILITIES, Capability

_REGISTRY_REL = "scripts/capability_test/registry.py"


def engine_root() -> Path:
    """Return the PrivaCI repository root."""
    return _REPO_ROOT


def commercial_root() -> Path | None:
    """Return the sibling commercial repo when present."""
    sibling = engine_root().parent / "privaci-commercial"
    return sibling if sibling.is_dir() else None


def _repo_root(cap: Capability) -> Path | None:
    if cap.repo == "public":
        return engine_root()
    return commercial_root()


def validate_test_paths() -> list[str]:
    """Return issues for missing capability test paths."""
    issues: list[str] = []
    for cap in CAPABILITIES.values():
        root = _repo_root(cap)
        if root is None:
            issues.append(
                f"{cap.id}: commercial repo not found; cannot verify "
                f"{', '.join(cap.test_paths)}"
            )
            continue
        for rel in cap.test_paths:
            path = root / rel
            if not path.is_file():
                issues.append(f"{cap.id}: missing test path {rel}")
    return issues


def validate_ids() -> list[str]:
    """Return issues for malformed capability ids."""
    issues: list[str] = []
    for cap in CAPABILITIES.values():
        prefix = "public-" if cap.repo == "public" else "commercial-"
        if not cap.id.startswith(prefix):
            issues.append(f"{cap.id}: id must start with {prefix!r}")
        if cap.id != cap.id.lower():
            issues.append(f"{cap.id}: id must be lowercase kebab-case")
        if not cap.test_paths:
            issues.append(f"{cap.id}: must list at least one test_paths entry")
    return issues


def _registered_test_paths() -> set[str]:
    paths: set[str] = set()
    for cap in CAPABILITIES.values():
        paths.update(cap.test_paths)
    return paths


def _staged_added_test_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=A", "--name-only", "--", "tests/"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".py") and "/integration/" not in line
    ]


def _staged_paths() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def validate_new_tests_registered() -> list[str]:
    """Return issues when new unit tests are staged without a registry update."""
    staged = _staged_paths()
    if _REGISTRY_REL in staged:
        return []

    registered = _registered_test_paths()
    issues: list[str] = []
    for rel in _staged_added_test_files():
        if rel not in registered:
            issues.append(
                f"{rel}: new unit test file is not listed in any capability "
                f"test_paths; update {_REGISTRY_REL}"
            )
    return issues


def main() -> int:
    """Run all registry guards; print issues and return an exit code."""
    issues = [
        *validate_ids(),
        *validate_test_paths(),
        *validate_new_tests_registered(),
    ]
    if not issues:
        return 0
    print("Capability registry check failed:", file=sys.stderr)
    for issue in issues:
        print(f"  - {issue}", file=sys.stderr)
    print(
        "\nWhen adding a user-facing capability, register it in "
        f"{_REGISTRY_REL} and run ./scripts/capability-test-suite.sh quick.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
