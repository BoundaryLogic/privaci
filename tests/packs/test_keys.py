"""Tests for config-pack trust-anchor resolution."""

from __future__ import annotations

import pytest

from privaci.packs.keys import PACK_PUBLIC_KEY_ENV, load_trusted_pack_public_key
from tests.fixtures.constants import FIXTURE_PACK_PUBLIC_KEY_HEX


def test_loads_valid_hex_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv(PACK_PUBLIC_KEY_ENV, FIXTURE_PACK_PUBLIC_KEY_HEX)

    # Act
    key = load_trusted_pack_public_key()

    # Assert
    assert key == bytes.fromhex(FIXTURE_PACK_PUBLIC_KEY_HEX)
    assert key is not None and len(key) == 32


def test_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv(PACK_PUBLIC_KEY_ENV, raising=False)

    # Act & Assert
    assert load_trusted_pack_public_key() is None


@pytest.mark.parametrize(
    "bad",
    ["not-hex-zz", "abcd", "00" * 31, "00" * 33, ""],
)
def test_returns_none_for_invalid_key(
    bad: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv(PACK_PUBLIC_KEY_ENV, bad)

    # Act & Assert
    assert load_trusted_pack_public_key() is None
