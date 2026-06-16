"""Unit tests for the Demo Corp fixture generator."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.fixtures.demo_corp.generate import build_data_sql, write_fixture_sql
from tests.fixtures.demo_corp.schema import ddl_sections
from tests.fixtures.demo_corp.seed import fixture_email, reset_seed
from tests.fixtures.demo_corp.tiers import TierName, tier_params


def test_fixture_email_uses_example_test_domain() -> None:
    """Arrange / Act / Assert: synthetic emails stay on example.test."""
    email = fixture_email("user", 1)

    assert email.endswith("@example.test")
    assert "gmail" not in email


def test_ddl_sections_include_all_schemas() -> None:
    """Arrange / Act / Assert: every application schema is represented."""
    names = [name for name, _ in ddl_sections()]
    combined = "\n".join(sql for _, sql in ddl_sections())

    assert "00_schemas.sql" in names
    assert "CREATE SCHEMA clinical" in combined
    assert "CREATE SCHEMA auth" in combined
    assert "PARTITION BY RANGE" in combined
    assert "PARTITION BY LIST" in combined


def test_build_data_sql_is_deterministic() -> None:
    """Arrange / Act / Assert: same tier produces identical SQL."""
    reset_seed()
    first = build_data_sql(TierName.MINI.value, scale=1)
    reset_seed()
    second = build_data_sql(TierName.MINI.value, scale=1)

    assert (
        hashlib.sha256(first.encode()).hexdigest()
        == hashlib.sha256(second.encode()).hexdigest()
    )


def test_write_fixture_sql_emits_numbered_files(tmp_path: Path) -> None:
    """Arrange / Act / Assert: generator writes schema + seed files."""
    paths = write_fixture_sql(tmp_path, TierName.MINI.value, scale=1)

    assert (tmp_path / "00_schemas.sql").exists()
    assert (tmp_path / "09_seed_data.sql").exists()
    assert len(paths) == len(ddl_sections()) + 1


@pytest.mark.parametrize(
    ("tier", "expected_users"),
    [
        (TierName.MINI, 200),
        (TierName.DEMO, 10_000),
    ],
)
def test_tier_params_user_counts(tier: TierName, expected_users: int) -> None:
    """Arrange / Act / Assert: tier presets match the spec table."""
    params = tier_params(tier)

    assert params.users == expected_users
