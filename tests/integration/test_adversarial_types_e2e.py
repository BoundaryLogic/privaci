"""Adversarial value/type coverage for the streaming + masking pipeline.

Exercises the engine against inputs that historically break naive COPY/stream
implementations: a deep foreign-key chain, 4-byte UTF-8 (emoji and
mathematical glyphs), large jsonb payloads, max-width numeric, arrays
containing quotes/commas, bytea, inet, and timestamptz. Non-PII columns must
round-trip byte-for-byte; PII (email) must be masked; integrity must hold.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from privaci.config.actions import FakeAction
from privaci.config.models import TableConfig
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import all_fks_valid, count_rows, value_present
from tests.integration.catalog_config import config_keep_only
from tests.integration.test_beta_gate_e2e import _load_sql

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_SCHEMA = "beta_adversarial"
_FK_TIERS = ("tier1", "tier2", "tier3", "tier4")
_TIER_ROWS = 5
_EXOTIC_ROWS = 25
# Columns whose values must survive masking untouched (everything but email).
_PASSTHROUGH_COLUMNS = (
    "id",
    "notes",
    "payload",
    "big_num",
    "money_val",
    "tags",
    "raw",
    "created_at",
    "ip",
)


async def _fetch_exotic(dsn: str) -> list[tuple[Any, ...]]:
    conn = await asyncpg.connect(dsn)
    try:
        cols = ", ".join(_PASSTHROUGH_COLUMNS)
        rows = await conn.fetch(
            f"SELECT {cols} FROM {_SCHEMA}.exotic ORDER BY id"  # noqa: S608
        )
        return [tuple(row) for row in rows]
    finally:
        await conn.close()


async def test_adversarial_dataset_round_trips_with_integrity(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange — deep FK chain + exotic-typed table, small batches to span reads.
    await _load_sql(source_dsn, "adversarial-types.sql")
    transforms: dict[str, TableConfig] = {
        f"{_SCHEMA}.{tier}": TableConfig() for tier in _FK_TIERS
    }
    transforms[f"{_SCHEMA}.exotic"] = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")},
    )
    config = await config_keep_only(
        source_dsn, transforms, auto_detect=False, batch_size=7
    )

    # Act
    summary = await run_masking_pipeline(
        source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
    )

    # Assert — every table fully streamed.
    for tier in _FK_TIERS:
        assert summary.table_row_counts[f"{_SCHEMA}.{tier}"] == _TIER_ROWS
    assert summary.table_row_counts[f"{_SCHEMA}.exotic"] == _EXOTIC_ROWS

    target = await asyncpg.connect(target_dsn)
    try:
        assert await all_fks_valid(target)
        for tier in _FK_TIERS:
            assert await count_rows(target, f"{_SCHEMA}.{tier}") == _TIER_ROWS
        assert await count_rows(target, f"{_SCHEMA}.exotic") == _EXOTIC_ROWS
        # PII was masked away.
        assert not await value_present(
            target, f"{_SCHEMA}.exotic", "email", "exotic1@example.test"
        )
    finally:
        await target.close()

    # Non-PII columns (jsonb, emoji text, max numeric, arrays, bytea, inet)
    # round-trip byte-for-byte through the COPY path.
    assert await _fetch_exotic(source_dsn) == await _fetch_exotic(target_dsn)
