"""Unit tests for the faker engine orchestration."""

from __future__ import annotations

import pytest

from privaci.errors import MaskingError
from privaci.mask.faker import FakeRequest, generate_fake
from tests.fixtures.constants import TEST_SALT


def _request(**overrides: object) -> FakeRequest:
    defaults = {
        "salt": TEST_SALT,
        "column_path": "public.users.email",
        "value": "user@acme.example",
        "provider": "email",
    }
    defaults.update(overrides)
    return FakeRequest(**defaults)  # type: ignore[arg-type]


def test_generate_fake_is_deterministic() -> None:
    # Arrange
    request = _request()

    # Act
    first = generate_fake(request)
    second = generate_fake(request)

    # Assert
    assert first == second
    assert "@" in first


def test_generate_fake_empty_string_unchanged() -> None:
    # Act
    result = generate_fake(_request(value=""))

    # Assert
    assert result == ""


def test_generate_fake_seed_alias_matches_referenced_path() -> None:
    # Arrange
    value = "user@acme.example"
    direct = _request(column_path="public.users.email", value=value)
    alias = _request(
        column_path="public.orders.customer_email",
        seed_alias="public.users.email",
        value=value,
    )

    # Act / Assert
    assert generate_fake(direct) == generate_fake(alias)


def test_generate_fake_different_paths_use_different_seeds() -> None:
    # Arrange
    from privaci.mask.faker.hash import compute_seed

    value = "user@acme.example"

    # Act
    users_seed = compute_seed(TEST_SALT, "public.users.email", value)
    customers_seed = compute_seed(TEST_SALT, "public.customers.email", value)

    # Assert — paths are mixed into the seed; library index collision is possible
    # but seeds themselves must always differ.
    assert users_seed != customers_seed


def test_generate_fake_different_paths_usually_differ_in_output() -> None:
    # Act — across many paths, outputs should not all collapse to one value.
    value = "user@acme.example"
    outputs = {
        generate_fake(_request(column_path=f"public.table{i}.email", value=value))
        for i in range(30)
    }

    # Assert
    assert len(outputs) > 1


def test_generate_fake_unique_email_all_distinct_inputs_unique() -> None:
    # Act — 200 distinct inputs on a UNIQUE column must not collide.
    outputs = {
        generate_fake(_request(value=f"user{i}@acme.example", is_unique=True))
        for i in range(200)
    }

    # Assert
    assert len(outputs) == 200


def test_generate_fake_unknown_provider_raises_masking_error() -> None:
    # Act / Assert
    with pytest.raises(MaskingError, match="Unknown provider"):
        generate_fake(_request(provider="not_a_real_provider"))
