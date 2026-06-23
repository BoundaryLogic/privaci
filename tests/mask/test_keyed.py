"""Tests for keyed masking actions (hmac_hash, pseudonym)."""

from __future__ import annotations

import pytest

from privaci.config.actions import HmacHashAction, PseudonymAction
from privaci.config.keyed import validate_keyed_actions
from privaci.config.models import Config, TableConfig
from privaci.contracts.base import LicenseStatus
from privaci.errors import LicenseError
from privaci.mask.column_masker import mask_column_value
from privaci.mask.keyed import compute_keyed_digest, normalize_for_hmac
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT

_TEST_KEY = "pseudonym-key-with-32-byte-minimum-length!!"


def test_hmac_hash_is_deterministic() -> None:
    action = HmacHashAction(action="hmac_hash")

    first = mask_column_value(
        "alice@acme.com",
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )
    second = mask_column_value(
        "alice@acme.com",
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )

    assert first == second
    assert first != "alice@acme.com"


def test_hmac_hash_differs_by_column_path() -> None:
    action = HmacHashAction(action="hmac_hash")
    value = "shared@acme.com"

    left = mask_column_value(
        value,
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )
    right = mask_column_value(
        value,
        action,
        salt=TEST_SALT,
        column_path="public.contacts.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )

    assert left != right


def test_pseudonym_looks_like_email() -> None:
    action = PseudonymAction(action="pseudonym", provider="email")

    masked = mask_column_value(
        "alice@acme.com",
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )

    assert "@" in masked
    assert masked != "alice@acme.com"
    digest = compute_keyed_digest(
        _TEST_KEY,
        "public.users.email",
        normalize_for_hmac("alice@acme.com"),
    )
    assert masked != digest.hex()


def test_pseudonym_seed_alias_matches_across_columns() -> None:
    action = PseudonymAction(
        action="pseudonym", provider="email", seed_alias="user_email"
    )

    users = mask_column_value(
        "alice@acme.com",
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )
    orders = mask_column_value(
        "alice@acme.com",
        action,
        salt=TEST_SALT,
        column_path="public.orders.customer_email",
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )

    assert users == orders


def test_key_rotation_changes_hmac_output() -> None:
    action = HmacHashAction(action="hmac_hash")
    value = "alice@acme.com"
    path = "public.users.email"

    first = mask_column_value(
        value,
        action,
        salt=TEST_SALT,
        column_path=path,
        is_unique=False,
        pseudonym_key=_TEST_KEY,
    )
    second = mask_column_value(
        value,
        action,
        salt=TEST_SALT,
        column_path=path,
        is_unique=False,
        pseudonym_key="different-pseudonym-key-32-chars-min!!",
    )

    assert first != second


def test_starter_tier_rejects_keyed_actions(mocker: pytest.Mock) -> None:
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        pseudonym_key=_TEST_KEY,
        tables={
            "public.users": TableConfig(
                columns={"email": HmacHashAction(action="hmac_hash")}
            )
        },
    )
    mocker.patch(
        "privaci.config.keyed.load_plugins"
    ).return_value.license_validator.validate.return_value = LicenseStatus(
        tier="starter",
        is_valid=True,
    )

    with pytest.raises(LicenseError, match="Growth tier"):
        validate_keyed_actions(config)
