"""Fixtures for Demo Corp end-to-end integration tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration._commercial_env import ensure_commercial_dev_license
from tests.integration.db_reset import reset_database

ensure_commercial_dev_license()

_DEMO_CORP_SQL_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "demo-corp"
)
DEMO_CORP_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "configs" / "demo-corp.yaml"
)
AUTODETECT_DEMO_CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "configs"
    / "autodetect-demo.yaml"
)
JSON_MASK_DEMO_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "configs" / "json-mask-demo.yaml"
)


async def _apply_sql_dir(dsn: str, sql_dir: Path) -> None:
    """Execute every ``*.sql`` file in ``sql_dir`` in lexicographic order."""
    import asyncpg

    paths = sorted(sql_dir.glob("*.sql"))
    conn = await asyncpg.connect(dsn)
    try:
        for path in paths:
            await conn.execute(path.read_text(encoding="utf-8"))
    finally:
        await conn.close()


async def _reset_target(dsn: str) -> None:
    """Drop user schemas on the target and restore bootstrap ``public``."""
    await reset_database(dsn)


@pytest.fixture
def spacy_ner_ready() -> None:
    """Require SpaCy + en_core_web_sm for demo-corp L2 masking tests."""
    from tests.integration.spacy_requirements import require_spacy_ner

    require_spacy_ner()


@pytest.fixture(scope="session")
def demo_corp_source_loaded(source_dsn: str, postgres_available: None) -> None:
    """Load the committed Demo Corp mini-tier SQL into the source database."""
    asyncio.run(_apply_sql_dir(source_dsn, _DEMO_CORP_SQL_DIR))


@pytest.fixture(scope="session")
def autodetect_demo_source_loaded(source_dsn: str, postgres_available: None) -> None:
    """Load the auto-detect demo schema (replaces prior source schemas)."""
    asyncio.run(_reset_target(source_dsn))
    sql_dir = (
        Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "autodetect-demo"
    )
    asyncio.run(_apply_sql_dir(source_dsn, sql_dir))


@pytest.fixture(scope="session")
def json_mask_demo_source_loaded(source_dsn: str, postgres_available: None) -> None:
    """Load the JSONB mask demo schema (replaces prior source schemas)."""
    asyncio.run(_reset_target(source_dsn))
    sql_dir = (
        Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "json-mask-demo"
    )
    asyncio.run(_apply_sql_dir(source_dsn, sql_dir))


@pytest.fixture
def clean_target(target_dsn: str, postgres_available: None) -> Iterator[None]:
    """Reset the target database before each integration test."""
    asyncio.run(_reset_target(target_dsn))
    yield
    if os.environ.get("CAPABILITY_PRESERVE_TARGET", "").strip() not in {
        "1",
        "yes",
        "true",
    }:
        asyncio.run(_reset_target(target_dsn))
