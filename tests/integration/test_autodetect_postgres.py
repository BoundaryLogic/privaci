"""Postgres integration tests for zero-config auto-detect."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.autodetect import resolve_effective_table_config, scan_catalog
from privaci.catalog.introspect import introspect_catalog
from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import assert_no_pii_present, fetch_column_values
from tests.integration.conftest import AUTODETECT_DEMO_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_TABLE = "autodetect_demo.contacts"
_FORBIDDEN_EMAILS = ("alice@example.test", "bob@example.test")


async def test_autodetect_assigns_fake_email_and_masks_on_postgres(
    source_dsn: str,
    target_dsn: str,
    autodetect_demo_source_loaded: None,
    clean_target: None,
) -> None:
    """Auto-detect must pick fake/email and the pipeline must apply it."""
    config = load_config(AUTODETECT_DEMO_CONFIG_PATH)

    source = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(source)
        detection = scan_catalog(catalog, config)
        finding = detection.finding_for(_TABLE, "email")
        assert finding is not None
        assert finding.confidence in {"high", "medium"}
        assert finding.action is not None
        assert finding.action.action == "fake"

        table = catalog.tables[_TABLE]
        effective = resolve_effective_table_config(table, config, detection)
        email_action = effective.columns["email"]
        assert email_action.action == "fake"
        assert getattr(email_action, "provider", None) == "email"
    finally:
        await source.close()

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        await assert_no_pii_present(
            target,
            _TABLE,
            "email",
            list(_FORBIDDEN_EMAILS),
        )
        statuses = await fetch_column_values(target, _TABLE, "status", limit=10)
        assert set(statuses) == {"active", "inactive"}
    finally:
        await target.close()
