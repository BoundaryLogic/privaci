"""Tests for scripts/check_ci_workflow_parity.py."""

from __future__ import annotations

from pathlib import Path

from tests.scripts.conftest_helpers import load_scripts_module

_mod = load_scripts_module("check_ci_workflow_parity", "check_ci_workflow_parity.py")


def _write_ok_tree(root: Path) -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        'run: |\n  ver="8.24.2"\n' '  curl ... "gitleaks_${ver}_linux_x64.tar.gz"\n',
        encoding="utf-8",
    )
    (workflows / "semgrep.yml").write_text(
        "container:\n  image: semgrep/semgrep:1.110.0\n"
        "run: >\n  semgrep scan --config=.semgrep.yml --config=auto "
        "--error --severity=ERROR src/privaci\n",
        encoding="utf-8",
    )
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/gitleaks/gitleaks\n"
        "    rev: v8.24.2\n",
        encoding="utf-8",
    )


def test_collect_flags_gitleaks_action(tmp_path: Path) -> None:
    # Arrange
    _write_ok_tree(tmp_path)
    wf = tmp_path / ".github" / "workflows" / "extra.yml"
    wf.write_text(
        "jobs:\n  x:\n    steps:\n" "      - uses: gitleaks/gitleaks-action@abc123\n",
        encoding="utf-8",
    )

    # Act
    findings = _mod.collect_parity_findings(tmp_path)

    # Assert
    assert any("gitleaks-action" in f for f in findings)


def test_collect_flags_codeql_workflow(tmp_path: Path) -> None:
    # Arrange
    _write_ok_tree(tmp_path)
    (tmp_path / ".github" / "workflows" / "codeql.yml").write_text(
        "name: CodeQL\n", encoding="utf-8"
    )

    # Act
    findings = _mod.collect_parity_findings(tmp_path)

    # Assert
    assert any("codeql.yml" in f for f in findings)


def test_collect_passes_calibrated_tree(tmp_path: Path) -> None:
    # Arrange
    _write_ok_tree(tmp_path)

    # Act
    findings = _mod.collect_parity_findings(tmp_path)

    # Assert
    assert findings == []
