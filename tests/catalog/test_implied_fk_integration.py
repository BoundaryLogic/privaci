"""Integration test for implied (soft) FK detection against Demo Corp."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from privaci.catalog import introspect_catalog

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_DEMO_CORP_SQL_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "demo-corp"
)
_SOURCE_COLUMN = "clinical.patient_documents.referring_provider_email"


async def _load_and_introspect(
    source_dsn: str, *, ignore: frozenset[str]
) -> dict[str, str]:
    from tests.integration.conftest import _apply_sql_dir

    await _apply_sql_dir(source_dsn, _DEMO_CORP_SQL_DIR)
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn, implied_fk_ignore=ignore)
    finally:
        await conn.close()
    return {
        warning.message: warning.code
        for warning in catalog.warnings
        if warning.code == "implied_fk_warning"
    }


async def test_demo_corp_emits_implied_fk_warning_for_provider_email(
    source_dsn: str, postgres_available: None
) -> None:
    # Act
    warnings = await _load_and_introspect(source_dsn, ignore=frozenset())

    # Assert
    assert any(
        "clinical.patient_documents" in msg
        and "seed_alias: clinical.providers.email" in msg
        for msg in warnings
    )


async def test_demo_corp_implied_fk_warning_silenced_by_ignore(
    source_dsn: str, postgres_available: None
) -> None:
    # Act
    warnings = await _load_and_introspect(
        source_dsn, ignore=frozenset({_SOURCE_COLUMN})
    )

    # Assert
    assert not any("referring_provider_email" in msg for msg in warnings)
