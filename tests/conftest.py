"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

pytest_plugins = ["tests.spikes.conftest", "tests.fixtures.conftest"]

import os

import pytest

from tests.fixtures.constants import TEST_SALT
from tests.integration._commercial_env import ensure_commercial_dev_license

# When a plugin-package license validator is installed locally, CLI unit tests
# that call execute_run need the same dev-license bypass as integration fixtures.
ensure_commercial_dev_license()
# Belt-and-suspenders: community mode ignores this; license-gated installs do not.
os.environ.setdefault("PRIVACI_COMMERCIAL_DEV_LICENSE", "1")


@pytest.fixture
def test_salt() -> str:
    """Deterministic salt for masking tests."""
    return TEST_SALT
