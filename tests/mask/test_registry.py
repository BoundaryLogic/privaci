"""Unit tests for the provider registry and config validation."""

from __future__ import annotations

import pytest

from privaci.config import Config
from privaci.errors import ConfigError
from privaci.mask.faker.base import FakeProvider
from privaci.mask.faker.registry import (
    get_provider,
    known_providers,
    register_provider,
    validate_fake_providers,
)
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


def test_known_providers_includes_builtins() -> None:
    # Assert
    names = known_providers()
    assert "email" in names
    assert "ssn" in names
    assert "credit_card" in names


def test_get_provider_returns_builtin() -> None:
    # Act
    provider = get_provider("first_name")

    # Assert
    assert provider.name == "first_name"


def test_get_provider_unknown_raises_key_error() -> None:
    # Act / Assert
    with pytest.raises(KeyError):
        get_provider("totally_unknown_provider_xyz")


def test_register_provider_custom() -> None:
    # Arrange
    class EchoProvider(FakeProvider):
        name = "test_echo_provider"

        def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
            return f"echo-{value}"

    register_provider(EchoProvider())

    # Act
    result = get_provider("test_echo_provider").generate(b"\x01" * 16, "x", params={})

    # Assert
    assert result == "echo-x"


def test_register_provider_rejects_empty_name() -> None:
    # Arrange
    class Bad(FakeProvider):
        name = ""

        def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
            return ""

    # Act / Assert
    with pytest.raises(ValueError, match="non-empty"):
        register_provider(Bad())


def test_validate_fake_providers_accepts_known() -> None:
    # Arrange
    config = Config.model_validate(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "tables": {
                "users": {
                    "columns": {
                        "email": {"action": "fake", "provider": "email"},
                        "password": {"action": "hash"},
                    }
                }
            },
        }
    )

    # Act / Assert — must not raise
    validate_fake_providers(config)


def test_validate_fake_providers_rejects_unknown() -> None:
    # Arrange
    config = Config.model_validate(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "tables": {
                "users": {
                    "columns": {"x": {"action": "fake", "provider": "no_such_provider"}}
                }
            },
        }
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="Unknown provider"):
        validate_fake_providers(config)
