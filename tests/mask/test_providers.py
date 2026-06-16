"""Unit tests for built-in fake providers."""

from __future__ import annotations

import re

import pytest

from privaci.mask.faker.hash import compute_seed
from privaci.mask.faker.providers.builtin import (
    is_fake_ssn,
    passes_luhn,
)
from privaci.mask.faker.registry import get_provider
from tests.fixtures.constants import TEST_SALT


def _fake(provider: str, value: str, *, path: str = "public.t.c") -> str:
    seed = compute_seed(TEST_SALT, path, value)
    return get_provider(provider).generate(seed, value, params={})


@pytest.mark.parametrize(
    "provider",
    [
        "first_name",
        "last_name",
        "full_name",
        "email",
        "phone",
        "street",
        "city",
        "postcode",
        "country",
        "address",
        "dob",
        "ip_address",
        "ssn",
        "credit_card",
        "uuid",
        "company",
        "job_title",
        "username",
        "password",
    ],
)
def test_builtin_provider_returns_non_empty(provider: str) -> None:
    # Act
    result = _fake(provider, "sample-input-value")

    # Assert
    assert result


def test_password_is_fixed_placeholder() -> None:
    # Act / Assert
    assert _fake("password", "anything") == "privaci-test-pw"


def test_email_uses_fake_domain() -> None:
    # Act
    result = _fake("email", "real@production.com")

    # Assert
    domain = result.split("@", maxsplit=1)[1]
    assert domain in {"fakedom.net", "example.test", "tryvault.dev"}


def test_ssn_in_test_range() -> None:
    # Act
    result = _fake("ssn", "123-45-6789")

    # Assert
    assert is_fake_ssn(result)
    area = int(result.split("-", maxsplit=1)[0])
    assert area <= 99


def test_credit_card_passes_luhn_and_test_bin() -> None:
    # Act
    result = _fake("credit_card", "4111111111111111")

    # Assert
    assert result.isdigit()
    assert passes_luhn(result)
    assert result.startswith(("411111", "424242", "555555", "378282", "601111"))


def test_phone_preserves_country_code() -> None:
    # Act
    result = _fake("phone", "+441234567890")

    # Assert
    assert result.startswith("+44")


def test_dob_is_iso_date() -> None:
    # Act
    result = _fake("dob", "1985-03-15")

    # Assert
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", result)


def test_uuid_is_valid_format() -> None:
    # Act
    result = _fake("uuid", "00000000-0000-0000-0000-000000000001")

    # Assert
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        result,
    )


def test_is_fake_ssn_rejects_real_range_area() -> None:
    # Assert
    assert not is_fake_ssn("123-45-6789")


def test_passes_luhn_rejects_invalid() -> None:
    # Assert
    assert not passes_luhn("4111111111111112")
    assert not passes_luhn("x")
    assert not passes_luhn("1")


def test_email_honors_domain_param() -> None:
    # Arrange
    seed = compute_seed(TEST_SALT, "public.users.email", "x@y.com")

    # Act
    result = get_provider("email").generate(
        seed, "x@y.com", params={"domain": "custom.example.test"}
    )

    # Assert
    assert result.endswith("@custom.example.test")


def test_is_fake_ssn_rejects_malformed() -> None:
    # Assert
    assert not is_fake_ssn("not-an-ssn")
