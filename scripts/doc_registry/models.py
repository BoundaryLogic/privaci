"""Document registry data models and shared path constants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs" / "registry.yaml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
ERRORS_PATH = REPO_ROOT / "src" / "privaci" / "errors.py"
ERROR_CODES_PATH = REPO_ROOT / "docs" / "error-codes.md"
PACKAGES_ROOT = REPO_ROOT / "src" / "privaci"
ISSUE_WAIVER_PATTERN = re.compile(r"issue\s+#\d+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """One row in ``docs/registry.yaml``."""

    id: str
    code: tuple[str, ...]
    docs: tuple[str, ...]
    changelog: str
    waiver: str | None


@dataclass(frozen=True, slots=True)
class Registry:
    """Parsed document registry."""

    exclude_packages: frozenset[str]
    entries: tuple[RegistryEntry, ...]
