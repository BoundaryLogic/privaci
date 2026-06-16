"""Unit tests for Tier-1 mini-schema builders."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.fixtures.builders import (
    MiniSchema,
    audit_events_no_pk,
    composite_pk_line_items,
    orgs_users_cycle,
    users_only,
)
from tests.fixtures.constants import DEMO_CORP_FORBIDDEN_EMAILS


@pytest.mark.parametrize(
    ("factory", "needle"),
    [
        (orgs_users_cycle, "DEFERRABLE INITIALLY DEFERRED"),
        (users_only, "CREATE TABLE mini_demo.users"),
        (composite_pk_line_items, "PRIMARY KEY (invoice_id, line_no)"),
        (audit_events_no_pk, "audit_log_events"),
    ],
)
def test_builder_emits_expected_ddl(
    factory: Callable[[], MiniSchema],
    needle: str,
) -> None:
    # Act
    build = factory()

    # Assert
    assert needle in build.ddl
    assert build.schema_name


def test_orgs_users_cycle_seed_uses_fixture_domain() -> None:
    # Act
    build = orgs_users_cycle()

    # Assert
    assert DEMO_CORP_FORBIDDEN_EMAILS[0].split("@")[1] in build.dml


def test_mini_schema_sql_joins_dml() -> None:
    # Arrange
    build = MiniSchema(schema_name="x", ddl="DDL;", dml="DML;")

    # Assert
    assert build.sql == "DDL;\nDML;"
