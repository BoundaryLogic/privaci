"""Validate ``.env.example`` keys appear in bound documentation."""

from __future__ import annotations

import re
from pathlib import Path

from doc_registry.models import ENV_EXAMPLE, REPO_ROOT, Registry

ENV_KEY_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]*)=")


def parse_env_example_keys(path: Path = ENV_EXAMPLE) -> list[str]:
    """Return active (non-comment) env keys from ``.env.example``."""
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_KEY_PATTERN.match(stripped)
        if match:
            keys.append(match.group(1))
    return keys


def check_env_keys(registry: Registry, repo_root: Path = REPO_ROOT) -> list[str]:
    """Ensure every ``.env.example`` key appears in bound env docs."""
    env_entry = next((e for e in registry.entries if e.id == "env-docs"), None)
    if env_entry is None:
        return ["registry missing env-docs entry for .env.example"]
    doc_text = ""
    for doc_path in env_entry.docs:
        full = repo_root / doc_path
        if full.is_file():
            doc_text += full.read_text(encoding="utf-8") + "\n"
    errors: list[str] = []
    for key in parse_env_example_keys(repo_root / ".env.example"):
        if key not in doc_text:
            errors.append(
                f".env.example key {key!r} not mentioned in env-docs pages: "
                f"{', '.join(env_entry.docs)}"
            )
    return errors
