"""Sync ``PrivaCIError`` exit codes and doc anchors with ``docs/error-codes.md``."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from doc_registry.models import ERROR_CODES_PATH, ERRORS_PATH, REPO_ROOT

HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
EXPLICIT_ANCHOR_PATTERN = re.compile(r"\{#([a-z0-9-]+)\}")


@dataclass(frozen=True, slots=True)
class ErrorDocBinding:
    """One ``PrivaCIError`` subclass binding of exit code to doc anchor."""

    class_name: str
    exit_code: int
    default_doc_anchor: str


def slugify_heading(text: str) -> str:
    """Convert a markdown heading to a GitHub-style anchor slug."""
    lowered = text.lower().strip()
    cleaned = re.sub(r"[^\w\s-]", "", lowered.replace("/", " "))
    return re.sub(r"[\s_]+", "-", cleaned).strip("-")


def collect_error_code_anchors(error_codes_path: Path = ERROR_CODES_PATH) -> set[str]:
    """Collect anchor ids present in ``docs/error-codes.md``."""
    text = error_codes_path.read_text(encoding="utf-8")
    anchors = set(EXPLICIT_ANCHOR_PATTERN.findall(text))
    for match in HEADING_PATTERN.finditer(text):
        anchors.add(slugify_heading(match.group(1)))
    return anchors


def _constant_int(node: ast.expr) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _constant_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _assign_targets_name(stmt: ast.Assign, name: str) -> bool:
    for target in stmt.targets:
        if isinstance(target, ast.Name) and target.id == name:
            return True
    return False


def _binding_from_class(node: ast.ClassDef) -> ErrorDocBinding | None:
    exit_code: int | None = None
    anchor: str | None = None
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            if _assign_targets_name(stmt, "exit_code"):
                code = _constant_int(stmt.value)
                if code is not None:
                    exit_code = code
            if _assign_targets_name(stmt, "default_doc_anchor"):
                text = _constant_str(stmt.value)
                if text is not None:
                    anchor = text
            continue
        if not isinstance(stmt, ast.AnnAssign):
            continue
        if not isinstance(stmt.target, ast.Name) or stmt.value is None:
            continue
        if stmt.target.id == "exit_code":
            code = _constant_int(stmt.value)
            if code is not None:
                exit_code = code
        elif stmt.target.id == "default_doc_anchor":
            text = _constant_str(stmt.value)
            if text is not None:
                anchor = text
    if exit_code is None or anchor is None:
        return None
    return ErrorDocBinding(
        class_name=node.name,
        exit_code=exit_code,
        default_doc_anchor=anchor,
    )


def _bindings_from_ast(source: str) -> list[ErrorDocBinding]:
    tree = ast.parse(source)
    bindings: list[ErrorDocBinding] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        binding = _binding_from_class(node)
        if binding is not None:
            bindings.append(binding)
    return bindings


def collect_privaci_error_bindings(
    errors_path: Path = ERRORS_PATH,
) -> list[ErrorDocBinding]:
    """Return exit_code + default_doc_anchor pairs from ``PrivaCIError`` subclasses."""
    try:
        source = errors_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"cannot read {errors_path}: {exc}") from exc
    try:
        return _bindings_from_ast(source)
    except SyntaxError as exc:
        raise SyntaxError(f"cannot parse {errors_path}: {exc}") from exc


def collect_privaci_error_anchors(
    errors_path: Path = ERRORS_PATH,
) -> set[str]:
    """Return every ``default_doc_anchor`` declared on ``PrivaCIError`` subclasses."""
    bindings = collect_privaci_error_bindings(errors_path)
    return {binding.default_doc_anchor for binding in bindings}


def anchor_documented(anchor: str, doc_anchors: set[str]) -> bool:
    """Return True when an error anchor is represented in error-codes.md."""
    if anchor in doc_anchors:
        return True
    # Require a hyphen boundary so ``exit-code-1`` does not match ``exit-code-10``.
    return any(existing.startswith(f"{anchor}-") for existing in doc_anchors)


def exit_code_section_documented(exit_code: int, doc_anchors: set[str]) -> bool:
    """Return True when docs include an ``exit-code-N-…`` section for ``exit_code``."""
    prefix = f"exit-code-{exit_code}"
    return any(
        anchor == prefix or anchor.startswith(f"{prefix}-") for anchor in doc_anchors
    )


def check_exit_code_anchors(
    errors_path: Path = ERRORS_PATH,
    error_codes_path: Path = ERROR_CODES_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Fail when exit codes or anchors are missing from ``docs/error-codes.md``."""
    if not error_codes_path.is_file():
        return [f"missing {error_codes_path.relative_to(repo_root).as_posix()}"]
    doc_anchors = collect_error_code_anchors(error_codes_path)
    errors: list[str] = []
    try:
        bindings = collect_privaci_error_bindings(errors_path)
    except (OSError, SyntaxError) as exc:
        return [str(exc)]
    seen_codes: set[int] = set()
    for binding in bindings:
        if not anchor_documented(binding.default_doc_anchor, doc_anchors):
            errors.append(
                f"docs/error-codes.md missing anchor for {binding.class_name}: "
                f"{binding.default_doc_anchor!r} (add heading or "
                f"{{#{binding.default_doc_anchor}}})"
            )
        if binding.exit_code in seen_codes:
            continue
        seen_codes.add(binding.exit_code)
        if not exit_code_section_documented(binding.exit_code, doc_anchors):
            errors.append(
                f"docs/error-codes.md missing exit-code-{binding.exit_code}-… "
                f"section for {binding.class_name} (exit_code={binding.exit_code})"
            )
    return errors
