"""Server-side bulk dataset builder for the 1 GB load test (OpenSpec §18.3).

The dataset is generated entirely inside PostgreSQL with
``INSERT ... SELECT FROM generate_series(...)`` so the Python process never
materialises the rows. This is the only memory-safe way to stand up a
multi-gigabyte fixture: the database streams generated rows straight to its own
heap/TOAST storage while Python holds nothing larger than the SQL statement.

The shape is deliberately representative of a real customer table — a small
parent (``organizations``) and a wide child (``customers``) carrying PII
(email/full_name/ssn) plus a large free-text ``bio`` that supplies most of the
bytes. ``bio`` is built from concatenated md5 hashes: high-entropy text that
does not compress away, so ``pg_total_relation_size`` tracks the requested
target closely.
"""

from __future__ import annotations

import asyncpg

LOADTEST_SCHEMA = "load_test"
ORGANIZATIONS_TABLE_NAME = "organizations"
CUSTOMERS_TABLE_NAME = "customers"
ORGANIZATIONS_TABLE = f"{LOADTEST_SCHEMA}.{ORGANIZATIONS_TABLE_NAME}"
CUSTOMERS_TABLE = f"{LOADTEST_SCHEMA}.{CUSTOMERS_TABLE_NAME}"

# A leak probe: the first customer's email always has this exact value, so the
# test can assert the original PII never reaches the target.
PROBE_EMAIL = "customer1@example.test"

_ORG_COUNT = 100

# Rows generated per INSERT statement. Large enough for throughput, small
# enough that one batch is a bounded WAL transaction (~100 MB of new rows).
_BATCH_ROWS = 100_000

# Table names below are fixed literals (no interpolation) so this file carries
# no SQL-injection surface; the public constants above mirror them for callers.
_DDL = """
DROP SCHEMA IF EXISTS load_test CASCADE;
CREATE SCHEMA load_test;

CREATE TABLE load_test.organizations (
    id   bigint PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE load_test.customers (
    id        bigserial PRIMARY KEY,
    org_id    bigint NOT NULL REFERENCES load_test.organizations (id),
    email     text NOT NULL UNIQUE,
    full_name text NOT NULL,
    ssn       text NOT NULL,
    bio       text NOT NULL
);
"""

_SEED_ORGS = """
INSERT INTO load_test.organizations (id, name)
SELECT g, 'Organization ' || g
FROM generate_series(1, $1::int) g;
"""

# 32 concatenated md5 hashes == 1024 chars of incompressible text. Combined
# with the other columns each row is ~1.1 KB, so ~1 GiB needs ~1M rows.
_INSERT_BATCH = """
INSERT INTO load_test.customers (org_id, email, full_name, ssn, bio)
SELECT
    ((g % $3::bigint) + 1),
    'customer' || g || '@example.test',
    'Customer Number ' || g,
    lpad((g % 1000000000)::bigint::text, 9, '0'),
    md5((g * 2)::text) || md5((g * 3)::text) || md5((g * 5)::text)
        || md5((g * 7)::text) || md5((g * 11)::text) || md5((g * 13)::text)
        || md5((g * 17)::text) || md5((g * 19)::text) || md5((g * 23)::text)
        || md5((g * 29)::text) || md5((g * 31)::text) || md5((g * 37)::text)
        || md5((g * 41)::text) || md5((g * 43)::text) || md5((g * 47)::text)
        || md5((g * 53)::text) || md5((g * 59)::text) || md5((g * 61)::text)
        || md5((g * 67)::text) || md5((g * 71)::text) || md5((g * 73)::text)
        || md5((g * 79)::text) || md5((g * 83)::text) || md5((g * 89)::text)
        || md5((g * 97)::text) || md5((g * 101)::text) || md5((g * 103)::text)
        || md5((g * 107)::text) || md5((g * 109)::text) || md5((g * 113)::text)
        || md5((g * 127)::text) || md5((g * 131)::text)
FROM generate_series($1::bigint, $2::bigint) g;
"""


async def build_loadtest_dataset(
    conn: asyncpg.Connection,
    target_bytes: int,
    *,
    batch_rows: int = _BATCH_ROWS,
) -> int:
    """Build the load-test schema server-side until it reaches ``target_bytes``.

    Generates ``customers`` rows in batches, checking the on-disk relation size
    (heap + TOAST + indexes) between batches and stopping once the table meets
    or exceeds ``target_bytes``. All generation happens inside PostgreSQL.

    Args:
        conn: An open connection to the source database.
        target_bytes: Minimum desired ``pg_total_relation_size`` for the
            customers table, in bytes.
        batch_rows: Number of rows to insert per statement.

    Returns:
        The total number of ``customers`` rows generated.
    """
    await conn.execute(_DDL)
    await conn.execute(_SEED_ORGS, _ORG_COUNT)

    generated = 0
    while True:
        size = await conn.fetchval(
            "SELECT pg_total_relation_size($1::regclass)", CUSTOMERS_TABLE
        )
        if int(size or 0) >= target_bytes:
            break
        start = generated + 1
        end = generated + batch_rows
        await conn.execute(_INSERT_BATCH, start, end, _ORG_COUNT)
        generated = end
    return generated


async def customers_relation_size(conn: asyncpg.Connection) -> int:
    """Return the current total on-disk size of the customers table in bytes."""
    size = await conn.fetchval(
        "SELECT pg_total_relation_size($1::regclass)", CUSTOMERS_TABLE
    )
    return int(size or 0)
