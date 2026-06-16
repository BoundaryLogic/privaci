"""Tests for column-name pattern matching."""

from __future__ import annotations

import pytest

from privaci.autodetect.matcher import match_column_name


@pytest.mark.parametrize(
    ("column_name", "rule_id"),
    [
        ("email", "email"),
        ("customer_email", "email_suffix"),
        ("agent_notes", "notes_suffix"),
        ("visit_notes", "notes_suffix"),
        ("password_hash", "password_hash"),
        ("api_key", "api_key"),
        ("name", "name_exact"),
        ("ip_address", "ip_address"),
        ("last_login_ip", "ip_suffix"),
        ("remote_ip", "ip_suffix"),
        ("ip", "ip_exact"),
    ],
)
def test_match_column_name_hits_expected_rule(
    column_name: str,
    rule_id: str,
) -> None:
    # Act
    rule = match_column_name(column_name)

    # Assert
    assert rule is not None
    assert rule.rule_id == rule_id


def test_match_column_name_returns_none_for_id() -> None:
    # Act
    rule = match_column_name("id")

    # Assert
    assert rule is None


@pytest.mark.parametrize("column_name", ["description", "shipping_status", "recipient"])
def test_ip_does_not_false_match_substrings(column_name: str) -> None:
    # Act
    rule = match_column_name(column_name)

    # Assert
    assert rule is None or rule.provider != "ip_address"


@pytest.mark.parametrize(
    "column_name",
    ["company_name", "hotel_name", "cancel_reason", "parcel_id"],
)
def test_bounded_tokens_avoid_common_false_positives(column_name: str) -> None:
    # Act
    rule = match_column_name(column_name)

    # Assert
    assert rule is None or rule.provider not in {"credit_card", "phone"}


def test_pan_matches_delimited_column_names() -> None:
    # Act
    rule = match_column_name("credit_pan")

    # Assert
    assert rule is not None
    assert rule.rule_id == "pan"


def test_ip_address_not_matched_as_street_address() -> None:
    # Act
    rule = match_column_name("ip_address")

    # Assert
    assert rule is not None
    assert rule.provider == "ip_address"
