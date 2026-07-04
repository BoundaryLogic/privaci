"""Tests for commercial docs sync into MkDocs."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_sync_module():
    """Import scripts/sync_commercial_docs.py without a scripts package."""
    path = ROOT / "scripts" / "sync_commercial_docs.py"
    spec = importlib.util.spec_from_file_location("sync_commercial_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_quick_launch_template_copies_yaml(tmp_path: Path) -> None:
    # Arrange
    module = _load_sync_module()
    commercial_root = tmp_path / "commercial-docs-source"
    template_dir = commercial_root / "infra/marketplace-quick-launch"
    template_dir.mkdir(parents=True)
    template = template_dir / "quick-launch.yaml"
    template.write_text("AWSTemplateFormatVersion: '2010-09-09'\n", encoding="utf-8")
    output_dir = tmp_path / "docs" / "commercial"
    module._OUTPUT_DIR = output_dir

    # Act
    dest = module._sync_quick_launch_template(commercial_root)

    # Assert
    assert dest == output_dir / "assets" / "quick-launch.yaml"
    assert dest.read_text(encoding="utf-8") == template.read_text(encoding="utf-8")


def test_sync_commercial_docs_includes_quick_launch_from_sibling_repo() -> None:
    # Arrange
    sibling_repo = "privaci" + "-commercial"
    commercial_root = ROOT.parent / sibling_repo
    if not commercial_root.is_dir():
        return
    module = _load_sync_module()
    original_output = module._OUTPUT_DIR
    output_dir = ROOT / "docs" / "commercial"
    module._OUTPUT_DIR = output_dir

    try:
        # Act
        synced, quick_launch = module.sync_commercial_docs(
            commercial_root=commercial_root
        )

        # Assert
        assert synced
        assert quick_launch.is_file()
        assert quick_launch.name == "quick-launch.yaml"
        assert "AWSTemplateFormatVersion" in quick_launch.read_text(encoding="utf-8")
    finally:
        module._OUTPUT_DIR = original_output
