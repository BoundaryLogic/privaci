# ADR-0006: Stream via PostgreSQL `COPY ... (FORMAT BINARY)`

## Status

Accepted — 2026-05-28

## Context

The engine must move billions of rows from source to target while
masking each row in flight. The streaming layer is the throughput
bottleneck for any large customer. Wrong choice here means rewrite,
not refactor.

Alternatives considered:

- **`OFFSET`/`LIMIT` pagination + batched INSERTs** — degrades
  quadratically as offsets grow. Unusable on large tables.
- **Keyset pagination (`WHERE pk > last_seen ORDER BY pk LIMIT n`) +
  batched INSERTs** — predictable, throughput ~10–20k rows/sec.
  Simple, works without superuser privileges. Backup if COPY-binary
  proves problematic.
- **PostgreSQL logical replication (`pg_logical`)** — would give CDC
  for free, but the product is explicitly batch-only, and logical
  replication requires `wal_level=logical`, which many managed
  Postgres tiers (RDS at lower tiers) don't enable.
- **`pg_dump` + restore + post-mask** — masking would have to happen
  on dumped data on disk, violating the "no intermediate masked data
  on disk" security requirement.
- **`COPY ... (FORMAT BINARY)` on both sides with in-process mutation**
  — fastest path, preserves type fidelity, keeps memory constant.

## Decision

The streaming layer uses:

- **Source side:** `COPY <table> (cols...) TO STDOUT (FORMAT BINARY)`,
  consumed via `asyncpg` `copy_from_query` streaming.
- **Target side:** `COPY <table> (cols...) FROM STDIN (FORMAT BINARY)`,
  fed via `asyncpg` `copy_to_table` streaming.
- **Between them:** an in-process Python pipeline that:
  1. Decodes a binary row into typed Python values.
  2. Passes the row through the masking pipeline.
  3. Re-encodes the masked row into binary.

Source and target COPY operations run concurrently within a single
asyncio event loop. Backpressure is enforced via a bounded async
queue.

A purpose-built binary codec covers the type catalog declared in
`streaming-pipeline/spec.md`. Unsupported types (PostGIS geometry,
custom domains) trigger a per-table fallback to text COPY with an
audit-log entry.

## Consequences

### Trade-offs accepted

- **Binary codec complexity.** PostgreSQL's binary COPY format is
  documented but type-by-type, and a few types have peculiar encodings
  (`numeric`, `timestamptz` with infinity, arrays). Implementing the
  codec is ~1 week of work.
- **`asyncpg` is required.** Cannot trivially fall back to `psycopg`
  later without rewriting this layer. Acceptable because `asyncpg` is
  the de facto async Postgres driver in 2026.

### Why this is worth the work

- **10–50× faster than batched INSERTs** for bulk load — the difference
  between "ran overnight" and "ran during the morning sprint" for a
  100 GB source.
- **Constant memory.** Exactly one batch (default 10k rows) is in RAM
  at a time, regardless of source size.
- **Type fidelity.** Binary format preserves `bytea`, `numeric`,
  `jsonb`, `timestamptz` precision exactly. No string-encode/decode
  round-trip surprises.

### Per-batch checkpoint integration

- Each batch commit writes:
  1. The masked rows via the target COPY.
  2. The last-PK-value to `_privaci.table_checkpoints`.
- Both writes are in the same target transaction so a crash leaves
  state consistent.

### Failure handling

- Source connection drop: retry the current batch 3× with exponential
  backoff. If all fail, exit `1` with the underlying error and the
  failed batch's starting PK in the audit log.
- Target connection drop: same.
- COPY protocol error: log the offending row's PK and column path
  (never the value), abort the table, mark as `failed` in
  checkpoints. The run continues with the next table.

### Memory contract

Batch bounds, backpressure, and operator sizing guidance are documented in
[ADR-0010](0010-constant-memory-streaming.md) and
[`docs/architecture/memory-model.md`](../architecture/memory-model.md).

### Future considerations

- If the in-Python codec proves to be the bottleneck (CPython is slow
  at byte manipulation), rewrite the codec as a `pyo3` Rust extension.
  The rest of the pipeline (asyncpg, masking) stays unchanged. v1.5+.
