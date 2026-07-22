"""Tests for scripts/check_mkdocs_doc_links.py."""

from __future__ import annotations

from pathlib import Path

from tests.scripts.conftest_helpers import load_scripts_module

_mod = load_scripts_module("check_mkdocs_doc_links", "check_mkdocs_doc_links.py")


def test_collect_flags_relative_link_outside_docs(tmp_path: Path) -> None:
    # Arrange
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "See [Constitution](../CONSTITUTION.md).\n",
        encoding="utf-8",
    )
    (tmp_path / "CONSTITUTION.md").write_text("# C\n", encoding="utf-8")

    # Act
    findings = _mod.collect_out_of_docs_links(docs)

    # Assert
    assert len(findings) == 1
    assert "CONSTITUTION.md" in findings[0]
    assert "leaves docs/" in findings[0]


def test_collect_allows_in_docs_and_https(tmp_path: Path) -> None:
    # Arrange
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "other.md").write_text("# O\n", encoding="utf-8")
    (docs / "page.md").write_text(
        "See [other](other.md) and "
        "[root](https://github.com/BoundaryLogic/privaci/blob/main/CONSTITUTION.md).\n",
        encoding="utf-8",
    )

    # Act
    findings = _mod.collect_out_of_docs_links(docs)

    # Assert
    assert findings == []
