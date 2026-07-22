"""Document registry validation package for ``scripts/check_doc_registry.py``."""

from __future__ import annotations

from doc_registry.coupling import check_coupling, entry_has_waiver
from doc_registry.env_keys import check_env_keys, parse_env_example_keys
from doc_registry.exit_anchors import (
    EXPLICIT_ANCHOR_PATTERN,
    HEADING_PATTERN,
    ErrorDocBinding,
    anchor_documented,
    check_exit_code_anchors,
    collect_error_code_anchors,
    collect_privaci_error_anchors,
    collect_privaci_error_bindings,
    slugify_heading,
)
from doc_registry.git_diff import collect_changed_files, resolve_merge_base
from doc_registry.globs import path_matches_glob, unsupported_glob_reason
from doc_registry.load import RegistryLoadError, load_registry
from doc_registry.models import (
    ERROR_CODES_PATH,
    ERRORS_PATH,
    PACKAGES_ROOT,
    REGISTRY_PATH,
    REPO_ROOT,
    Registry,
    RegistryEntry,
)
from doc_registry.run import run_checks
from doc_registry.structure import (
    check_package_coverage,
    list_top_level_packages,
    pattern_covers_package,
    validate_structure,
)

__all__ = [
    "ERROR_CODES_PATH",
    "ERRORS_PATH",
    "EXPLICIT_ANCHOR_PATTERN",
    "ErrorDocBinding",
    "HEADING_PATTERN",
    "PACKAGES_ROOT",
    "REGISTRY_PATH",
    "REPO_ROOT",
    "Registry",
    "RegistryEntry",
    "RegistryLoadError",
    "anchor_documented",
    "check_coupling",
    "check_env_keys",
    "check_exit_code_anchors",
    "check_package_coverage",
    "collect_changed_files",
    "collect_error_code_anchors",
    "collect_privaci_error_anchors",
    "collect_privaci_error_bindings",
    "entry_has_waiver",
    "list_top_level_packages",
    "load_registry",
    "parse_env_example_keys",
    "path_matches_glob",
    "pattern_covers_package",
    "resolve_merge_base",
    "run_checks",
    "slugify_heading",
    "unsupported_glob_reason",
    "validate_structure",
]
