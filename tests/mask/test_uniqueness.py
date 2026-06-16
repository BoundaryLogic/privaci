"""Unit tests for UNIQUE-aware suffix strategies."""

from __future__ import annotations

from privaci.mask.faker.hash import compute_seed
from privaci.mask.faker.uniqueness import apply_uniqueness, uniqueness_suffix
from tests.fixtures.constants import TEST_SALT


def test_uniqueness_suffix_is_sixteen_hex_chars() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.email", "x@y.com")

    # Act
    suffix = uniqueness_suffix(seed)

    # Assert — 64 bits keeps collisions negligible at 1M+ rows.
    assert len(suffix) == 16
    assert int(suffix, 16) >= 0


def test_apply_uniqueness_email_inserts_plus_tag() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.email", "john@fake.tld")

    # Act
    result = apply_uniqueness("john@fake.tld", seed, provider="email")

    # Assert
    assert "+@" not in result
    assert "+" in result.split("@", maxsplit=1)[0]
    assert result.endswith("@fake.tld")


def test_apply_uniqueness_text_appends_double_underscore() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.first_name", "Alex")

    # Act
    result = apply_uniqueness("Alex", seed, provider="first_name")

    # Assert
    assert "__" in result
    assert result.startswith("Alex__")


def test_apply_uniqueness_numeric_preserves_width() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.items.id", "12345")

    # Act
    result = apply_uniqueness("12345", seed, provider="hash")

    # Assert
    assert len(result) == 5
    assert result.isdigit()


def test_apply_uniqueness_email_without_at_sign() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.email", "localonly")

    # Act
    result = apply_uniqueness("localonly", seed, provider="email")

    # Assert
    assert result.startswith("localonly+")


def test_unique_numeric_empty_width_returns_unchanged() -> None:
    # Arrange
    from privaci.mask.faker.uniqueness import _unique_numeric

    # Act
    result = _unique_numeric("", compute_seed(TEST_SALT, "public.items.id", ""))

    # Assert
    assert result == ""


def test_apply_uniqueness_dob_returns_valid_iso_date() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "clinical.patients.dob", "1950-01-08")

    # Act
    result = apply_uniqueness("1948-10-18", seed, provider="dob")

    # Assert
    assert "__" not in result
    parts = result.split("-")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_apply_uniqueness_password_unchanged() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.password_hash", "x")

    # Act
    result = apply_uniqueness("privaci-test-pw", seed, provider="password")

    # Assert
    assert result == "privaci-test-pw"
