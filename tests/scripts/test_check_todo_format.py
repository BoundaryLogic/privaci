"""Tests for the todo-requires-issue pre-commit guard script.

Malformed-marker fixtures are assembled from the script's own marker constant so
that this test file never contains a literal bare marker the hook would flag.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(filename: str):
    path = _REPO_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_module = _load_script_module("check_todo_format.py")
_find = _module.find_offending_todos
_MARKER = _module._TODO_MARKER
_BAD = f"{_MARKER}jd): fix this later"  # missing issue number
_GOOD = f"{_MARKER}jd): make async — see #42"


def test_flags_added_todo_without_issue_number() -> None:
    # Arrange
    diff = f"+++ b/src/x.py\n+    value = 1  {_BAD}\n"

    # Act
    offenders = _find(diff)

    # Assert
    assert offenders == [f"value = 1  {_BAD}"]


def test_accepts_well_formed_todo() -> None:
    # Arrange
    diff = f"+    value = 1  {_GOOD}\n"

    # Act / Assert
    assert _find(diff) == []


def test_ignores_removed_line() -> None:
    # A removed line (leading "-") is never a newly added TODO.
    assert _find(f"-    value = 1  {_BAD}\n") == []


def test_ignores_unchanged_context_line() -> None:
    # A context line (leading space) is unchanged, not added.
    assert _find(f"     value = 1  {_BAD}\n") == []


def test_ignores_diff_file_header() -> None:
    # "+++" headers start with "+" but are not source content.
    assert _find("+++ b/some_file.py\n") == []


@pytest.mark.parametrize("clean", ["+    clean_code = 2", "+    x = 'no marker here'"])
def test_ignores_lines_without_marker(clean: str) -> None:
    # Act / Assert
    assert _find(f"{clean}\n") == []
