"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

pytest_plugins = ["tests.spikes.conftest", "tests.fixtures.conftest"]

import pytest

from tests.fixtures.constants import TEST_SALT


@pytest.fixture
def test_salt() -> str:
    """Deterministic salt for masking tests."""
    return TEST_SALT
