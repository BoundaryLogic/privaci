"""Orchestrate all document registry validation checks."""

from __future__ import annotations

from pathlib import Path

from doc_registry.coupling import check_coupling
from doc_registry.env_keys import check_env_keys
from doc_registry.exit_anchors import check_exit_code_anchors
from doc_registry.git_diff import collect_changed_files
from doc_registry.load import RegistryLoadError, load_registry
from doc_registry.models import REPO_ROOT
from doc_registry.structure import check_package_coverage, validate_structure


def run_checks(
    *,
    staged: bool = False,
    skip_coupling: bool = False,
    base_sha: str | None = None,
    repo_root: Path = REPO_ROOT,
    registry_path: Path | None = None,
    changed_files: frozenset[str] | None = None,
) -> list[str]:
    """Run all registry checks and return human-readable errors."""
    reg_path = registry_path or (repo_root / "docs" / "registry.yaml")
    errors: list[str] = []
    try:
        registry = load_registry(reg_path)
    except RegistryLoadError as exc:
        return [f"failed to load registry: {exc}"]
    errors.extend(validate_structure(registry, repo_root))
    errors.extend(check_package_coverage(registry, repo_root / "src" / "privaci"))
    errors.extend(check_env_keys(registry, repo_root))
    errors.extend(
        check_exit_code_anchors(
            repo_root / "src" / "privaci" / "errors.py",
            repo_root / "docs" / "error-codes.md",
            repo_root,
        )
    )
    if changed_files is None:
        paths, coupling_errors = collect_changed_files(
            staged=staged,
            skip_coupling=skip_coupling,
            base_sha=base_sha,
            repo_root=repo_root,
        )
        errors.extend(coupling_errors)
        if paths is not None and not skip_coupling:
            errors.extend(check_coupling(registry, paths))
    elif not skip_coupling:
        errors.extend(check_coupling(registry, changed_files))
    return errors
