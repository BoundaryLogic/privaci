"""Tests for generate-ci template emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from privaci.cli.generate_ci import generate_ci_files
from privaci.errors import ConfigError


def test_generate_github_actions_writes_workflow_and_docs(tmp_path: Path) -> None:
    # Act
    paths = generate_ci_files("github-actions", output_dir=tmp_path)

    # Assert
    assert (tmp_path / ".github" / "workflows" / "privaci-refresh.yml") in paths
    assert (tmp_path / "docs" / "privaci-setup.md") in paths
    workflow = (tmp_path / ".github" / "workflows" / "privaci-refresh.yml").read_text()
    assert "privaci run" in workflow
    assert "SOURCE_DB_URL" in workflow


def test_generate_gitlab_ci_writes_pipeline(tmp_path: Path) -> None:
    # Act
    paths = generate_ci_files("gitlab-ci", output_dir=tmp_path)

    # Assert
    assert paths == [tmp_path / ".gitlab-ci.yml"]
    assert "privaci run" in paths[0].read_text()


def test_generate_k8s_cronjob_writes_manifest(tmp_path: Path) -> None:
    # Act
    paths = generate_ci_files("k8s-cronjob", output_dir=tmp_path)

    # Assert
    assert paths[0].name == "privaci-cronjob.yaml"
    assert "kind: CronJob" in paths[0].read_text()


def test_unknown_platform_raises_config_error() -> None:
    # Act / Assert
    with pytest.raises(ConfigError):
        generate_ci_files("circle-ci", output_dir=Path("."))
