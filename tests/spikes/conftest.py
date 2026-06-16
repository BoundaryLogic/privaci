"""Shared fixtures for Week-1 spike integration tests."""

from __future__ import annotations

import pytest

from privaci.spikes._env import dsn_from_env

_DEFAULT_SOURCE = "postgresql://postgres:dev@localhost:55432/privaci_source"
_DEFAULT_TARGET = "postgresql://postgres:dev@localhost:55433/privaci_target"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "spike: Week-1 architecture spikes (requires Postgres and/or SpaCy model)",
    )


@pytest.fixture(scope="session")
def source_dsn() -> str:
    """Source Postgres URL (env var or compose.dev.yml default)."""
    return dsn_from_env("SOURCE_DB_URL") or _DEFAULT_SOURCE


@pytest.fixture(scope="session")
def target_dsn() -> str:
    """Target Postgres URL (env var or compose.dev.yml default)."""
    return dsn_from_env("TARGET_DB_URL") or _DEFAULT_TARGET


@pytest.fixture(scope="session")
def postgres_available(source_dsn: str, target_dsn: str) -> None:
    """Skip spike DB tests when compose Postgres is not reachable."""
    import asyncpg

    async def _probe() -> None:
        for dsn in (source_dsn, target_dsn):
            conn = await asyncpg.connect(dsn, timeout=3)
            await conn.close()

    try:
        import asyncio

        asyncio.run(_probe())
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
