"""Unit tests for run-identity fingerprint helpers."""

from __future__ import annotations

import pytest

from privaci.config import Config
from privaci.state.fingerprints import (
    config_hash,
    generate_uuid7,
    salt_fingerprint,
    source_db_hash,
)
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT


def test_salt_fingerprint_is_16_chars_and_deterministic() -> None:
    # Arrange
    salt = TEST_SALT

    # Act
    first = salt_fingerprint(salt)
    second = salt_fingerprint(salt)

    # Assert
    assert len(first) == 16
    assert first == second


def test_salt_fingerprint_differs_by_salt() -> None:
    # Arrange
    salt_a = TEST_SALT
    salt_b = TEST_SALT + "-rotated"

    # Act / Assert
    assert salt_fingerprint(salt_a) != salt_fingerprint(salt_b)


def test_salt_fingerprint_never_contains_salt() -> None:
    # Arrange
    salt = TEST_SALT

    # Act
    fingerprint = salt_fingerprint(salt)

    # Assert
    assert salt not in fingerprint


@pytest.mark.parametrize(
    ("url_a", "url_b", "expect_equal"),
    [
        (
            "postgresql://u:p@db.example.com:5432/prod",
            "postgresql://other:secret@db.example.com:5432/prod",
            True,  # credentials are excluded
        ),
        (
            "postgresql://u:p@db.example.com:5432/prod_main",
            "postgresql://u:p@db.example.com:5432/prod_analytics",
            False,  # different database name
        ),
        (
            "postgresql://u:p@db.example.com/prod",
            "postgresql://u:p@db.example.com:5432/prod",
            True,  # default port is applied
        ),
        (
            "postgresql://u:p@DB.EXAMPLE.COM:5432/prod",
            "postgresql://u:p@db.example.com:5432/prod",
            True,  # host is case-insensitive
        ),
    ],
)
def test_source_db_hash_identity(url_a: str, url_b: str, expect_equal: bool) -> None:
    # Act
    hash_a = source_db_hash(url_a)
    hash_b = source_db_hash(url_b)

    # Assert
    assert (hash_a == hash_b) is expect_equal


def test_source_db_hash_is_sha256_hex() -> None:
    # Act
    digest = source_db_hash("postgresql://u:p@host:5432/db")

    # Assert
    assert len(digest) == 64
    assert int(digest, 16) >= 0


def test_config_hash_is_order_independent() -> None:
    # Arrange
    config_a = Config(version=SUPPORTED_CONFIG_VERSION, batch_size=500)
    config_b = Config(batch_size=500, version=SUPPORTED_CONFIG_VERSION)

    # Act / Assert
    assert config_hash(config_a) == config_hash(config_b)


def test_config_hash_changes_with_content() -> None:
    # Arrange
    config_a = Config(version=SUPPORTED_CONFIG_VERSION, batch_size=500)
    config_b = Config(version=SUPPORTED_CONFIG_VERSION, batch_size=1000)

    # Act / Assert
    assert config_hash(config_a) != config_hash(config_b)


def test_generate_uuid7_sets_version_and_variant() -> None:
    # Act
    value = generate_uuid7()

    # Assert
    assert value.version == 7
    assert (value.int >> 62) & 0b11 == 0b10  # RFC 9562 variant


def test_generate_uuid7_is_unique_and_time_ordered() -> None:
    # Act
    first = generate_uuid7()
    second = generate_uuid7()

    # Assert
    assert first != second
    # 48-bit timestamp prefix is non-decreasing between successive calls.
    assert (second.int >> 80) >= (first.int >> 80)
