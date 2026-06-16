"""Fixtures for secret resolver tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from privaci.secrets.types import SecretRedactionFilter


@pytest.fixture(autouse=True)
def _clear_redaction_patterns() -> None:
    SecretRedactionFilter.clear_registered_secrets()
    yield
    SecretRedactionFilter.clear_registered_secrets()


@pytest.fixture(autouse=True)
def _allow_tmp_secret_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow file:// reads under pytest's tmp_path in unit tests."""
    monkeypatch.setenv("PRIVACI_SECRET_FILE_ROOTS", str(tmp_path))
