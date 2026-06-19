## Context

The COPY-binary pipeline already decodes rows in-process. File sinks replace
the target COPY leg with an encoder implementing the same batch interface
used for checkpoint commits (checkpoints still persist to `_privaci` on a
configured state target or embedded SQLite — see runner design).

## Goals / Non-Goals

**Goals:**

- Stream masked rows to Parquet or JSONL without loading full tables.
- Preserve catalog column names and logical types in Parquet schema.
- Support `sink-only` runs (source DB + file out) and `dual-write` (file +
  relational target) for Business tier.
- Tier gate at validation.

**Non-Goals:**

- Avro, ORC, CSV export (CSV input is S3 connector change).
- Unmasked export or "raw dump" mode.
- Splitting one table across multiple files by partition key (single file per
  table in v1; partition tables still one file per child).

## Decisions

### D1. Shared `RowSink` interface

**Decision:** `RowSink.write_batch(rows) -> None`, `RowSink.finalize()`.
Parquet and JSONL implement it; runner swaps target COPY for sink.

### D2. pyarrow for Parquet

**Decision:** Use `pyarrow` for schema inference and chunked writes. Pin exact
version in requirements.

**Alternatives:** fastparquet (less maintained). Pure Python Parquet (too much scope).

### D3. Checkpoints with file sinks

**Decision:** Checkpoints and audit still require a `state_target` DSN
(default: same as relational target when dual-write; required separate
minimal Postgres or existing target when sink-only). Document in config.

### D4. Dual-write is Business+

**Decision:** Writing both DB target and file sink in one run requires
Business or Enterprise tier. Sink-only also Business+.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Disk fills mid-run | Pre-flight statvfs on local paths; fail loud |
| Parquet type coercion errors | Fall back to string column with audit warning |
| Large wide tables | Reuse batch auto-tune from streaming spec |

## Open Questions

- Embedded state for sink-only without any Postgres target? — defer; v1
  requires a small state DB or reuse source (read-only violation). Prefer
  mandatory `STATE_DB_URL` for sink-only.
