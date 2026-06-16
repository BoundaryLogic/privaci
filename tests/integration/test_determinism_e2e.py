"""End-to-end determinism and salt-isolation guarantees on real Postgres.

Two properties an operator relies on:

* **Idempotency** — masking the same source with the same salt twice produces
  byte-identical output. A regression here means hidden randomness (e.g. an
  accidental ``random``/``uuid4`` call) crept into a masker.
* **Salt isolation** — rotating the salt re-keys every fake value, so a leaked
  output set cannot be correlated back across salts.
"""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH, _reset_target

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# A second salt that satisfies the >= 32 char rule and is distinct from TEST_SALT.
_ROTATED_SALT = "b" * 64


async def _snapshot_masked_users(dsn: str) -> list[tuple[object, ...]]:
    """Return masked PII columns for every user, ordered by primary key."""
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch("""
            SELECT id, email, ssn, phone, password_hash
            FROM public.users
            ORDER BY id
            """)
        return [tuple(row) for row in rows]
    finally:
        await conn.close()


async def _run(source_dsn: str, target_dsn: str, salt: str) -> None:
    config = load_config(DEMO_CORP_CONFIG_PATH)
    await run_masking_pipeline(
        source_dsn, target_dsn, config, salt, audit_enabled=False
    )


async def test_same_salt_produces_identical_output(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    # Arrange / Act — mask the same source twice with the same salt.
    await _run(source_dsn, target_dsn, TEST_SALT)
    first = await _snapshot_masked_users(target_dsn)

    await _reset_target(target_dsn)
    await _run(source_dsn, target_dsn, TEST_SALT)
    second = await _snapshot_masked_users(target_dsn)

    # Assert — fully deterministic: no row, no column differs.
    assert first, "expected masked users in the target"
    assert first == second


async def test_salt_rotation_changes_fake_output(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    # Arrange / Act — mask with two different salts.
    await _run(source_dsn, target_dsn, TEST_SALT)
    base = await _snapshot_masked_users(target_dsn)

    await _reset_target(target_dsn)
    await _run(source_dsn, target_dsn, _ROTATED_SALT)
    rotated = await _snapshot_masked_users(target_dsn)

    # Assert — every fake email is re-keyed by the salt, so the columns diverge.
    base_emails = [row[1] for row in base]
    rotated_emails = [row[1] for row in rotated]
    assert base_emails != rotated_emails
