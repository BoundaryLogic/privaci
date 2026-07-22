"""Minimal document-registry tree for checker unit tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

_DOC_STUBS: tuple[tuple[str, str], ...] = (
    ("docs/configuration.md", "SOURCE_DB_URL\n"),
    (
        "docs/error-codes.md",
        "## Exit code 1: Generic error {#exit-code-1-generic-error}\n",
    ),
    ("docs/cli-reference.md", "cli\n"),
    ("docs/generated/cli-reference.md", "cli\n"),
    ("docs/deployment.md", "deploy\n"),
    ("docs/local-development.md", "dev\n"),
    ("docs/test-fixtures.md", "fixtures\n"),
    ("docs/adr/0014-project-constitution.md", "adr\n"),
    ("docs/ci-gates.md", "gates\n"),
    ("docs/quality-evidence.md", "quality\n"),
    ("docs/architecture/memory-model.md", "mem\n"),
    ("docs/generated/configuration-reference.md", "cfg\n"),
)

_REGISTRY_BODY = """\
entries:
  - id: constitution
    code:
      - CONSTITUTION.md
    docs:
      - docs/adr/0014-project-constitution.md
      - docs/ci-gates.md
      - docs/quality-evidence.md
  - id: env-docs
    code:
      - .env.example
    docs:
      - docs/configuration.md
      - docs/cli-reference.md
      - docs/deployment.md
      - docs/local-development.md
      - docs/test-fixtures.md
      - docs/generated/cli-reference.md
  - id: errors
    code:
      - src/privaci/errors.py
    docs:
      - docs/error-codes.md
      - docs/generated/errors/**
    changelog: required
  - id: cli
    code:
      - src/privaci/cli/**
    docs:
      - docs/cli-reference.md
      - docs/generated/cli-reference.md
    changelog: required
  - id: mask
    code:
      - src/privaci/mask/**
    docs:
      - docs/configuration.md
      - docs/architecture/memory-model.md
    changelog: required
"""


def _seed_packages(root: Path, extra_package: str | None) -> None:
    packages = root / "src" / "privaci"
    for name in ("mask", "cli", "spikes"):
        (packages / name).mkdir(parents=True, exist_ok=True)
    if extra_package:
        (packages / extra_package).mkdir(parents=True, exist_ok=True)


def _seed_docs_and_env(root: Path) -> None:
    for rel, body in _DOC_STUBS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (root / "docs" / "generated" / "errors").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "generated" / "configuration").mkdir(parents=True, exist_ok=True)
    (root / "CONSTITUTION.md").write_text("# Constitution\n", encoding="utf-8")
    (root / ".env.example").write_text(
        "SOURCE_DB_URL=postgresql://x\n", encoding="utf-8"
    )
    (root / "src" / "privaci" / "errors.py").write_text(
        textwrap.dedent("""\
            class PrivaCIError(Exception):
                exit_code = 1
                default_doc_anchor = "exit-code-1-generic-error"
            """),
        encoding="utf-8",
    )


def write_min_registry(
    root: Path,
    *,
    extra_package: str | None = None,
    exclude_spikes: bool = True,
) -> None:
    """Create a tiny repo tree that satisfies structure/coverage checks."""
    _seed_packages(root, extra_package)
    _seed_docs_and_env(root)
    exclude_block = "      - spikes\n" if exclude_spikes else "      []\n"
    registry = f"meta:\n  exclude_packages:\n{exclude_block}{_REGISTRY_BODY}"
    (root / "docs" / "registry.yaml").write_text(registry, encoding="utf-8")
