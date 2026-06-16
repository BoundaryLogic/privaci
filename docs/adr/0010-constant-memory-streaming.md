# ADR-0010: Constant-memory streaming bounds

## Status

Accepted — 2026-06-08

## Context

PrivaCI runs as a **one-shot batch job** in customer VPCs (Docker, Kubernetes
CronJob, CI). Customers size memory from container limits or VM RAM. The
product is sold on a **flat monthly price per source database** — the engine
must not consume unbounded compute on large sources.

A 100 GB PostgreSQL database is a normal customer workload. Loading entire
tables into memory, or buffering unbounded rows between source and target,
would make the product undeployable on modest instances and violate the
security rule that **intermediate masked data must not be written to disk**.

[ADR-0006](0006-copy-binary-streaming.md) chose COPY-binary streaming for
throughput and type fidelity. This ADR records the **memory contract** that
the streaming layer must uphold, independent of source database size.

## Decision

The streaming engine SHALL maintain **constant-memory** behavior:

1. **Batch-bound row data.** At most one active batch of decoded rows is in
   RAM per table (or partition child) stream. Default batch size: **10,000
   rows**.

2. **Byte cap per batch.** Auto-tune batch size so estimated in-memory batch
   bytes stay **≤ 256 MB**. Hard ceiling: **1 GB** per batch (design risk R11,
   very wide tables).

3. **Backpressure.** Source and target COPY operations run concurrently in
   one asyncio loop. A **bounded async queue** between them SHALL pause the
   source COPY when the target cannot keep pace — never grow an unbounded
   in-process buffer.

4. **No disk staging.** Masked row data SHALL NOT be written to temporary
   files or intermediate volumes.

5. **Sequential table streams (MVP).** One table's row stream is active in
   the hot path at a time. Schema catalog metadata for all tables may reside
   in memory (metadata-only, not row data).

6. **Verifiable bound.** Integration tests (§12, §18) SHALL assert that RSS
   during a large-table run remains bounded by
   `batch_size × row_size + fixed_overhead`, not by total source size.

Customer-facing documentation lives in
[`docs/architecture/memory-model.md`](../architecture/memory-model.md).

## Consequences

### What scales with source size

- **Wall-clock time** and **network/IO** — not RAM.
- **Checkpoint and audit rows** in `_privaci` on the target (stored in Postgres,
  not held in engine memory).

### What does not scale with source size

- Active row batch in the COPY pipeline.
- Per-batch masking work (L1 regex/faker, L2 SpaCy on current batch only).

### Fixed overhead (plan for it)

| Component | Order of magnitude |
|-----------|-------------------|
| Python + asyncpg | ~100–200 MB |
| Schema catalog | ~1–50 MB typical |
| SpaCy `en_core_web_sm` (if L2 enabled) | ~50–150 MB |

### Operator controls

- Global and per-table `batch_size` in `mask-rules.yaml`.
- Disabling L2 (passthrough or L1-only) avoids loading SpaCy.
- Kubernetes `resources.limits.memory` should exceed expected RSS by a
  headroom margin (see memory-model doc).

### Trade-offs accepted

- **Lower default throughput on wide rows** when auto-tune shrinks batches.
- **User overrides can increase RAM** if `batch_size` is set very high; auto-tune
  and the 1 GB cap are safety nets, not a substitute for sensible limits.
- **Keyset-pagination fallback** (ADR-0006) trades throughput for the same
  batch-bound memory model when COPY-binary is unavailable for a table.

### Related ADRs

- [ADR-0006](0006-copy-binary-streaming.md) — COPY-binary transport mechanism.
- [ADR-0009](0009-postgres-native-partitioning.md) — partition children as
  independent streaming units.
