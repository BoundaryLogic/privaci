"""Contract tests for deployment artifacts (no image build required)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_uses_non_root_user_and_entrypoint() -> None:
    # Arrange
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    # Assert
    assert "python:3.12-slim" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert 'ENTRYPOINT ["privaci"]' in dockerfile
    assert "en_core_web_sm" in dockerfile
    assert "EXPOSE" not in dockerfile


def test_compose_privaci_service_is_read_only_with_tmpfs() -> None:
    # Arrange
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")

    # Assert
    assert "read_only: true" in compose
    assert "tmpfs:" in compose
    assert "dockerfile: Dockerfile" in compose or "context: ." in compose


def test_helm_chart_has_cronjob_and_secret_refs() -> None:
    # Arrange
    cronjob = (ROOT / "deploy/helm/privaci/templates/cronjob.yaml").read_text(
        encoding="utf-8"
    )
    values = (ROOT / "deploy/helm/privaci/values.yaml").read_text(encoding="utf-8")

    # Assert
    assert "kind: CronJob" in cronjob
    assert "secretKeyRef" in cronjob
    assert "readOnlyRootFilesystem: true" in values
    assert "sourceDbUrlSecret" in values
