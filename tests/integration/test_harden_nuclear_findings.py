"""Integration cells for nuclear-harden schema/resume findings."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest
import yaml

from privaci.cli._errors import run_cli
from privaci.cli._run import execute_run
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT

pytestmark = [pytest.mark.integration]

_SCHEMA = "harden_nuclear"
_PARENT = f"{_SCHEMA}.parents"
_CHILD = f"{_SCHEMA}.children"
_CHECKED = f"{_SCHEMA}.checked"


async def _reset_source(conn: asyncpg.Connection) -> None:
    await conn.execute(f'DROP SCHEMA IF EXISTS "{_SCHEMA}" CASCADE')
    await conn.execute(f'CREATE SCHEMA "{_SCHEMA}"')
    await conn.execute(f"""
        CREATE TABLE "{_SCHEMA}".parents (
            id integer PRIMARY KEY
        )
        """)
    await conn.execute(f"""
        CREATE TABLE "{_SCHEMA}".children (
            id integer PRIMARY KEY,
            parent_id integer REFERENCES "{_SCHEMA}".parents (id)
        )
        """)
    await conn.execute(f"""
        CREATE TABLE "{_SCHEMA}".checked (
            id integer PRIMARY KEY,
            email text NOT NULL,
            CONSTRAINT checked_email_chk CHECK (email <> '')
        )
        """)
    await conn.execute(f'INSERT INTO "{_SCHEMA}".parents (id) VALUES (1)')  # noqa: S608
    await conn.execute(
        f'INSERT INTO "{_SCHEMA}".children (id, parent_id) VALUES (1, 1)'  # noqa: S608
    )
    await conn.execute(f"""
        INSERT INTO "{_SCHEMA}".checked (id, email)
        VALUES (1, 'demo@example.test')
        """)  # noqa: S608


@pytest.fixture
async def harden_source(source_dsn: str) -> None:
    conn = await asyncpg.connect(source_dsn)
    try:
        await _reset_source(conn)
    finally:
        await conn.close()


def _config(**updates: object) -> Config:
    base = Config(
        version="1.0",
        auto_detect=False,
        replicate_views=False,
        replicate_functions=False,
        tables={
            _PARENT: TableConfig(strategy="exclude"),
            _CHILD: TableConfig(null_orphan_fks=True),
            _CHECKED: TableConfig(),
        },
    )
    return base.model_copy(update=updates)


@pytest.mark.asyncio
async def test_check_constraint_round_trip(
    source_dsn: str,
    target_dsn: str,
    harden_source: None,
    clean_target: None,
) -> None:
    config = _config(
        tables={
            _CHECKED: TableConfig(),
        }
    )

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        definition = await target.fetchval(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class rel ON rel.oid = c.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = $1
              AND rel.relname = 'checked'
              AND c.conname = 'checked_email_chk'
            """,
            _SCHEMA,
        )
        assert definition is not None
        assert "CHECK" in definition.upper()
    finally:
        await target.close()


@pytest.mark.asyncio
async def test_null_orphan_fks_nulls_child_column(
    source_dsn: str,
    target_dsn: str,
    harden_source: None,
    clean_target: None,
) -> None:
    config = _config(on_existing_data="truncate")

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        parent_id = await target.fetchval(
            f'SELECT parent_id FROM "{_SCHEMA}".children WHERE id = 1'  # noqa: S608
        )
        assert parent_id is None
        fk_exists = await target.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = $1
                  AND rel.relname = 'children'
                  AND c.contype = 'f'
            )
            """,
            _SCHEMA,
        )
        assert fk_exists is False
    finally:
        await target.close()


@pytest.mark.asyncio
async def test_require_binary_conflicts_with_orphan_nulling(
    source_dsn: str,
    target_dsn: str,
    harden_source: None,
    clean_target: None,
) -> None:
    config = _config(passthrough_copy="require_binary", on_existing_data="truncate")

    with pytest.raises(PreflightError, match="null_orphan_fks|require_binary"):
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            config,
            TEST_SALT,
            audit_enabled=False,
        )


def test_force_restart_rejected_under_fail(
    source_dsn: str,
    target_dsn: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync test so ``execute_run`` can call ``asyncio.run`` on the main thread."""
    config_path = tmp_path / "mask-rules.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "auto_detect": False,
                "on_existing_data": "fail",
                "tables": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOURCE_DB_URL", source_dsn)
    monkeypatch.setenv("TARGET_DB_URL", target_dsn)
    monkeypatch.setenv("ANONYMIZATION_SALT", TEST_SALT)

    code = run_cli(
        lambda: execute_run(
            config_path=str(config_path),
            source=source_dsn,
            target=target_dsn,
            force_restart=True,
            audit_enabled=False,
        )
    )
    assert code == 2
