"""Tests for documentation generation scripts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs" / "generated"


def _load_generate_docs_module():
    """Import scripts/generate_docs.py without a scripts package."""
    path = ROOT / "scripts" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("generate_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_configuration_reference_lists_root_fields() -> None:
    # Arrange
    content = (GENERATED / "configuration-reference.md").read_text(encoding="utf-8")

    # Assert
    assert "AUTO-GENERATED" in content
    assert "`version`" in content
    assert "`tables`" in content


def test_generated_cli_reference_lists_run_command() -> None:
    # Arrange
    content = (GENERATED / "cli-reference.md").read_text(encoding="utf-8")

    # Assert
    assert "`privaci run`" in content
    assert "--prometheus-port" in content


def test_mask_rules_schema_json_is_valid() -> None:
    # Arrange
    raw = (GENERATED / "mask-rules.schema.json").read_text(encoding="utf-8")

    # Act
    schema = json.loads(raw)

    # Assert
    assert schema["title"] == "Config"
    assert "properties" in schema


def test_generate_docs_check_passes_when_committed() -> None:
    # Arrange
    outputs = _load_generate_docs_module()._outputs()

    # Assert — on-disk generated files match live code
    for path, content in outputs.items():
        assert path.exists()
        assert path.read_text(encoding="utf-8") == content


def test_generate_docs_script_check_exit_zero() -> None:
    # Act
    result = subprocess.run(  # noqa: S603 — fixed repo script path
        [sys.executable, str(ROOT / "scripts" / "generate_docs.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Assert
    assert result.returncode == 0, result.stderr
