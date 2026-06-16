"""Shared fixtures for config-pack tests."""

from __future__ import annotations

import pytest

from privaci.packs.keys import PACK_PUBLIC_KEY_ENV
from tests.fixtures.constants import FIXTURE_PACK_PUBLIC_KEY_HEX


@pytest.fixture(autouse=True)
def fixture_pack_trust_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the fixture public key as the trust anchor for pack tests.

    Production ships no embedded key, so signature verification needs the trust
    anchor supplied via the environment. Tests use the fixture public key that
    matches the signatures on packs under ``tests/fixtures/packs``.
    """
    monkeypatch.setenv(PACK_PUBLIC_KEY_ENV, FIXTURE_PACK_PUBLIC_KEY_HEX)
