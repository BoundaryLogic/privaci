#!/usr/bin/env python3
"""Load the Demo Corp sample schema and seed into the source database.

Reads ``SOURCE_DB_URL`` and applies ``tests/fixtures/sql/demo-corp/*.sql`` in
lexicographic order (regenerate with ``make fixtures-generate``). Re-running is
safe: the SQL drops and recreates every schema. Use this to give
``privaci catalog inspect`` a realistic schema to explore.

Example:
    SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/privaci_source \\
        python -m scripts.load_sample_data
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

from privaci.spikes._env import dsn_from_env

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("load_sample_data")

_SQL_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sql" / "demo-corp"
)


async def _apply(dsn: str, sql_paths: list[Path]) -> None:
    """Execute each SQL file in order against the source database."""
    conn = await asyncpg.connect(dsn)
    try:
        for path in sql_paths:
            logger.info("Applying %s", path.name)
            await conn.execute(path.read_text(encoding="utf-8"))
    finally:
        await conn.close()


def main() -> int:
    """Load the sample dataset; exit non-zero on misconfiguration."""
    dsn = dsn_from_env("SOURCE_DB_URL")
    if dsn is None:
        logger.error(
            "SOURCE_DB_URL is not set. Example:\n"
            "  SOURCE_DB_URL=postgresql://postgres:dev@127.0.0.1:55432/"
            "privaci_source python -m scripts.load_sample_data"
        )
        return 1

    sql_paths = sorted(_SQL_DIR.glob("*.sql"))
    if not sql_paths:
        logger.error("No SQL files found in %s", _SQL_DIR)
        return 1

    asyncio.run(_apply(dsn, sql_paths))
    logger.info("Done. Try: privaci catalog inspect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
