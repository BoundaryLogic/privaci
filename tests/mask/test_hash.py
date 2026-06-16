"""Unit tests for faker hash primitives."""

from __future__ import annotations

import pytest

from privaci.mask.faker.hash import (
    compute_seed,
    normalize_input,
    seed_to_index,
    seed_to_int,
)
from tests.fixtures.constants import TEST_SALT


def test_normalize_input_applies_nfc() -> None:
    # Arrange — composed vs decomposed unicode for é
    composed = "café"
    decomposed = "café"

    # Act / Assert
    assert normalize_input(composed) == normalize_input(decomposed)


def test_compute_seed_is_deterministic() -> None:
    # Act
    first = compute_seed(TEST_SALT, "public.users.email", "a@b.com")
    second = compute_seed(TEST_SALT, "public.users.email", "a@b.com")

    # Assert
    assert first == second
    assert len(first) == 16


def test_compute_seed_differs_by_column_path() -> None:
    # Act
    users = compute_seed(TEST_SALT, "public.users.email", "a@b.com")
    customers = compute_seed(TEST_SALT, "public.customers.email", "a@b.com")

    # Assert
    assert users != customers


def test_compute_seed_avoids_concatenation_ambiguity() -> None:
    # Act
    left = compute_seed("ab", "c", "d")
    right = compute_seed("a", "bc", "d")

    # Assert
    assert left != right


def test_compute_seed_differs_by_salt() -> None:
    # Act
    a = compute_seed(TEST_SALT, "public.users.email", "a@b.com")
    b = compute_seed(TEST_SALT + "x", "public.users.email", "a@b.com")

    # Assert
    assert a != b


def test_seed_to_index_within_bounds() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "x", "y")

    # Act
    index = seed_to_index(seed, 25)

    # Assert
    assert 0 <= index < 25


def test_seed_to_index_rejects_empty_library() -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="library_size"):
        seed_to_index(b"\x00" * 16, 0)


def test_seed_to_int_round_trip() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "a", "b")

    # Act / Assert
    assert seed_to_int(seed) >= 0
