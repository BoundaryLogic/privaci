"""File and function line-limit validation helpers."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from ci_gate_common import iter_privaci_py_files, load_issue_keyed_entries

REPO_ROOT = Path(__file__).resolve().parents[1]
WAIVER_PATH = REPO_ROOT / "scripts" / "file_limit_waivers.txt"
MAX_FILE_LINES = 400
MAX_FUNCTION_LINES = 40
INLINE_WAIVER_RE = re.compile(
    r"FILE_LIMIT_WAIVER:\s*issue\s+#(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Violation:
    """One file- or function-limit violation."""

    rel_path: str
    kind: str
    name: str
    line: int
    size: int


def iter_source_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    """Return ``src/privaci/**/*.py`` paths excluding spikes."""
    return iter_privaci_py_files(repo_root)


def load_waiver_file(path: Path | None = None) -> dict[str, int]:
    """Load ``path`` or ``path:function`` waivers from the waiver file."""
    waiver_path = path if path is not None else WAIVER_PATH
    return load_issue_keyed_entries(waiver_path)


def _inline_waivers(lines: list[str]) -> dict[int, int]:
    """Map function definition line numbers to issue ids from preceding comments."""
    waivers: dict[int, int] = {}
    for idx, text in enumerate(lines):
        match = INLINE_WAIVER_RE.search(text)
        if not match:
            continue
        next_idx = idx + 1
        while next_idx < len(lines) and not lines[next_idx].strip():
            next_idx += 1
        if next_idx < len(lines):
            waivers[next_idx + 1] = int(match.group(1))
    return waivers


def _function_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    if node.end_lineno is None or node.lineno is None:
        return 0
    return node.end_lineno - node.lineno + 1


def _is_function_waived(
    *,
    rel_path: str,
    function_name: str,
    line: int,
    file_waivers: dict[str, int],
    inline_waivers: dict[int, int],
) -> bool:
    """Whole-file waiver entries do NOT suppress per-function checks."""
    if f"{rel_path}:{function_name}" in file_waivers:
        return True
    return line in inline_waivers


def _file_size_violation(
    *,
    rel_path: str,
    line_count: int,
    file_waivers: dict[str, int],
) -> Violation | None:
    if line_count <= MAX_FILE_LINES or rel_path in file_waivers:
        return None
    return Violation(
        rel_path=rel_path,
        kind="file",
        name=rel_path,
        line=1,
        size=line_count,
    )


def _function_violations(
    *,
    rel_path: str,
    tree: ast.AST,
    file_waivers: dict[str, int],
    inline_waivers: dict[int, int],
) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        span = _function_length(node)
        if span <= MAX_FUNCTION_LINES:
            continue
        if _is_function_waived(
            rel_path=rel_path,
            function_name=node.name,
            line=node.lineno,
            file_waivers=file_waivers,
            inline_waivers=inline_waivers,
        ):
            continue
        violations.append(
            Violation(
                rel_path=rel_path,
                kind="function",
                name=node.name,
                line=node.lineno,
                size=span,
            )
        )
    return violations


def _empty_tree_violation() -> Violation:
    return Violation(
        rel_path="src/privaci",
        kind="file",
        name="",
        line=1,
        size=0,
    )


def _scan_one_file(
    path: Path,
    *,
    repo_root: Path,
    file_waivers: dict[str, int],
) -> list[Violation]:
    """Scan one source file for file/function limit violations."""
    rel = path.relative_to(repo_root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            Violation(
                rel_path=rel,
                kind="function",
                name=f"<unreadable: {exc}>",
                line=1,
                size=0,
            )
        ]
    lines = text.splitlines()
    violations: list[Violation] = []
    file_hit = _file_size_violation(
        rel_path=rel,
        line_count=len(lines),
        file_waivers=file_waivers,
    )
    if file_hit is not None:
        violations.append(file_hit)
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        violations.append(
            Violation(
                rel_path=rel,
                kind="function",
                name=f"<syntax-error: {exc.msg}>",
                line=exc.lineno or 1,
                size=0,
            )
        )
        return violations
    violations.extend(
        _function_violations(
            rel_path=rel,
            tree=tree,
            file_waivers=file_waivers,
            inline_waivers=_inline_waivers(lines),
        )
    )
    return violations


def collect_violations(repo_root: Path = REPO_ROOT) -> list[Violation]:
    """Scan the tree and return unwaived file/function limit violations."""
    base = repo_root / "src" / "privaci"
    if not base.is_dir() or not any(base.rglob("*.py")):
        return [_empty_tree_violation()]
    paths = iter_source_files(repo_root)
    file_waivers = load_waiver_file(repo_root / "scripts" / "file_limit_waivers.txt")
    violations: list[Violation] = []
    for path in paths:
        violations.extend(
            _scan_one_file(path, repo_root=repo_root, file_waivers=file_waivers)
        )
    return violations


def format_violations(violations: list[Violation]) -> list[str]:
    """Render violations as human-readable error strings."""
    messages: list[str] = []
    for item in violations:
        if item.kind == "file":
            if item.size == 0 and item.rel_path == "src/privaci":
                messages.append("src/privaci: no Python files found (excluding spikes)")
                continue
            messages.append(
                f"{item.rel_path}: file has {item.size} lines (max {MAX_FILE_LINES})"
            )
            continue
        messages.append(
            f"{item.rel_path}:{item.name} at line {item.line}: "
            f"{item.size} lines (max {MAX_FUNCTION_LINES})"
        )
    return messages
