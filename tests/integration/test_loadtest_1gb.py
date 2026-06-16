"""1 GB load test for the masking pipeline (OpenSpec §18.3).

Stands up a multi-gigabyte source dataset entirely server-side, runs the full
masking pipeline against it, and verifies the engine's headline operational
guarantees at scale:

* **Completeness** — every source row reaches the target (row parity).
* **Integrity** — no foreign key is left orphaned.
* **No leakage** — masked PII never survives into the target.
* **Bounded memory** — the Python process streams the whole dataset without
  loading it into memory; peak RSS growth during the run stays well under a
  ceiling that is a small fraction of the dataset size.

The dataset size and the memory ceiling are configurable via environment
variables so the same test runs cheaply in CI and at full 1 GiB scale on
demand:

* ``PRIVACI_LOADTEST_BYTES`` — target customers-table size (default 64 MiB).
* ``PRIVACI_LOADTEST_MEM_CEILING_MB`` — max allowed RSS growth (default 512).

This is a slow integration test; it is excluded from the default suite and run
with ``pytest -m "integration and slow"`` against the compose.dev.yml pair.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import asyncpg
import pytest

from privaci.catalog.identifiers import qualify
from privaci.config.actions import FakeAction
from privaci.config.models import Config, TableConfig
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import count_rows, value_present
from tests.integration.catalog_config import config_keep_only
from tests.integration.loadtest_data import (
    CUSTOMERS_TABLE,
    CUSTOMERS_TABLE_NAME,
    LOADTEST_SCHEMA,
    ORGANIZATIONS_TABLE,
    ORGANIZATIONS_TABLE_NAME,
    PROBE_EMAIL,
    build_loadtest_dataset,
    customers_relation_size,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.asyncio]

_LOG = logging.getLogger(__name__)
_MIB = 1024 * 1024
_DEFAULT_TARGET_BYTES = 64 * _MIB
_DEFAULT_CEILING_MB = 512
# Peak RSS growth must stay below this fraction (1/N) of the dataset size: proof
# the engine streams rather than buffering the whole table. Tunable in one place.
_MAX_RSS_DATASET_DIVISOR = 2


def _target_bytes() -> int:
    return int(os.environ.get("PRIVACI_LOADTEST_BYTES", _DEFAULT_TARGET_BYTES))


def _ceiling_bytes() -> int:
    mb = int(os.environ.get("PRIVACI_LOADTEST_MEM_CEILING_MB", _DEFAULT_CEILING_MB))
    return mb * _MIB


def _rss_bytes() -> int:
    """Return this process's RSS in bytes, or 0 where ``/proc`` is unavailable.

    Reads Linux ``/proc/self/status``; on non-Linux hosts (macOS, Windows) the
    file does not exist, so the sampler degrades to a no-op rather than failing.
    """
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return 0
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


class _PeakRssSampler:
    """Background thread that records the peak RSS while the pipeline runs."""

    _JOIN_TIMEOUT_SECONDS = 2

    def __init__(self, interval: float = 0.05) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.peak = 0

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _rss_bytes())
            self._stop.wait(self._interval)

    def __enter__(self) -> _PeakRssSampler:
        self.peak = _rss_bytes()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._JOIN_TIMEOUT_SECONDS)
        if self._thread.is_alive():
            _LOG.warning(
                f"Peak RSS sampler thread did not stop within "
                f"{self._JOIN_TIMEOUT_SECONDS}s; leaving the daemon thread to "
                "be reaped at interpreter exit."
            )


async def _loadtest_config(source_dsn: str) -> Config:
    """Keep only the load-test tables; mask customer PII, copy the rest."""
    return await config_keep_only(
        source_dsn,
        {
            ORGANIZATIONS_TABLE: TableConfig(),
            CUSTOMERS_TABLE: TableConfig(
                columns={
                    "email": FakeAction(action="fake", provider="email"),
                    "full_name": FakeAction(action="fake", provider="full_name"),
                    "ssn": FakeAction(action="fake", provider="ssn"),
                }
            ),
        },
        auto_detect=False,
        batch_size=2000,
    )


async def _orphaned_customers(conn: asyncpg.Connection) -> int:
    """Count customers whose org_id has no matching organization (fast anti-join)."""
    # Route the schema-qualified names through the same validating quoting used in
    # production SQL so this test cannot become an injection vector even if the
    # constants were ever changed to untrusted input.
    customers = qualify(LOADTEST_SCHEMA, CUSTOMERS_TABLE_NAME)
    organizations = qualify(LOADTEST_SCHEMA, ORGANIZATIONS_TABLE_NAME)
    value = await conn.fetchval(f"""
        SELECT count(*)::int FROM {customers} c
        WHERE NOT EXISTS (
            SELECT 1 FROM {organizations} o WHERE o.id = c.org_id
        )
        """)  # noqa: S608 — identifiers quoted via qualify(); never user input.
    return int(value or 0)


async def test_one_gb_dataset_streams_with_bounded_memory(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange — build the large dataset entirely server-side.
    target_bytes = _target_bytes()
    builder = await asyncpg.connect(source_dsn)
    try:
        row_count = await build_loadtest_dataset(builder, target_bytes)
        actual_bytes = await customers_relation_size(builder)
    finally:
        await builder.close()

    assert actual_bytes >= target_bytes
    config = await _loadtest_config(source_dsn)

    # Act — stream the whole dataset, sampling peak memory throughout.
    with _PeakRssSampler() as sampler:
        baseline_rss = sampler.peak
        summary = await run_masking_pipeline(
            source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
        )

    # Assert — completeness, integrity, no leakage, bounded memory.
    assert summary.table_row_counts[CUSTOMERS_TABLE] == row_count

    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, CUSTOMERS_TABLE) == row_count
        assert await _orphaned_customers(target) == 0
        assert not await value_present(target, CUSTOMERS_TABLE, "email", PROBE_EMAIL)
    finally:
        await target.close()

    rss_growth = max(0, sampler.peak - baseline_rss)
    ceiling = _ceiling_bytes()
    # Peak RSS growth must be a small fraction of the dataset — proof that the
    # engine streams rather than buffering the whole table in memory.
    assert rss_growth < ceiling, (
        f"RSS grew {rss_growth / _MIB:.2f} MiB streaming a "
        f"{actual_bytes / _MIB:.2f} MiB dataset (ceiling {ceiling / _MIB:.2f} MiB)"
    )
    assert rss_growth < actual_bytes // _MAX_RSS_DATASET_DIVISOR
