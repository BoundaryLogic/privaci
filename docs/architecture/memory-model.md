# Memory model

PrivaCI is designed to mask **very large PostgreSQL databases** (100 GB+)
without loading whole tables into RAM. Memory use scales with **row width
and batch size**, not with **total database size**.

> **Related decisions:** [ADR-0006](../adr/0006-copy-binary-streaming.md)
> (COPY-binary streaming) and
> [ADR-0010](../adr/0010-constant-memory-streaming.md) (batch bounds and
> backpressure).

## What you need to know

| Question | Answer |
|----------|--------|
| Will a 100 GB source need 100 GB of RAM? | **No.** Rows stream in fixed-size batches. |
| What drives RAM during a run? | Active batch size × average row width + fixed overhead (runtime, catalog, optional SpaCy model). |
| Is masked data written to disk? | **No.** Processing is in-memory streaming only (see security model below). |
| Can I tune memory vs throughput? | **Yes.** Set `batch_size` globally or per table in `mask-rules.yaml`. |

## How streaming works

```text
Source PostgreSQL          PrivaCI process              Target PostgreSQL
─────────────────          ───────────────              ─────────────────
COPY TO STDOUT (BINARY) →  decode → mask → encode  →  COPY FROM STDIN (BINARY)
   (async stream)              (one batch)                 (async stream)
```

1. PrivaCI opens a **streaming** `COPY ... TO STDOUT (FORMAT BINARY)` on the
   source for one table (or partition child).
2. Each batch of rows is decoded, masked in-process, and re-encoded.
3. Masked rows are fed to `COPY ... FROM STDIN (FORMAT BINARY)` on the target.
4. When the target is slower than the source, **backpressure** pauses the
   source COPY instead of buffering unbounded rows.
5. After each batch commits, checkpoint state (last primary-key value) is
   written to `_privaci.table_checkpoints` in the **same transaction**.

Only **one batch** of row data is hot in memory at a time per active stream.

### Passthrough-only tables

Tables with no masking (all columns `passthrough`, or no column rules) use a
**piped COPY-binary fast path**: source `COPY OUT` and target `COPY IN` run
concurrently, connected by a bounded in-process chunk queue (default depth 16).
Memory stays proportional to in-flight COPY chunks, not table size.

## Memory bound (simplified formula)

```text
RSS ≈ fixed_overhead + (batch_size × average_row_bytes) + masking_overhead
```

| Component | Typical size | Scales with DB size? |
|-------------|--------------|----------------------|
| Python runtime + `asyncpg` connections | ~100–200 MB | No |
| Schema catalog (tables, columns, FKs) | ~1–50 MB for most schemas | Metadata only (not row data) |
| SpaCy `en_core_web_sm` (Level 2 NER) | ~50–150 MB when loaded | No |
| Active streaming batch | **≤ 256 MB** auto-tuned (see below) | No |
| Level 3 `ai_refine` context windows | Small per request (commercial, opt-in) | No |

**Design target:** stream-mask a 100 GB database in **roughly 500 MB–1.5 GB
RSS** for typical schemas. Very wide rows or aggressive `batch_size`
overrides can push higher (hard cap: **1 GB per batch**).

## Batch sizing and auto-tune

Default batch size is **10,000 rows**. PrivaCI auto-tunes batch size
**downward** when:

- Estimated batch bytes would exceed **256 MB** (wide rows, large `text`/`jsonb`).
- The target-side queue blocks beyond a threshold (backpressure).

You can override batch size in config:

```yaml
# Global default
batch_size: 10000

tables:
  events:
    batch_size: 5000   # narrower memory footprint on a wide event table
  lookup_codes:
    batch_size: 50000  # small rows — higher throughput if memory allows
```

Auto-tune still applies when memory thresholds are hit, even with overrides.

### Example: wide-row table

A table with ~50 KB average row width:

- Default 10,000 rows × 50 KB ≈ **500 MB** per batch → too large.
- Auto-tune reduces batch size to ~5,000 rows → **≤ 256 MB** per batch.

## What does *not* grow with database size

- Row payloads during streaming (one batch at a time).
- Checkpoint records (last PK per table/partition, not full row history).
- Audit log entries (written incrementally to the target DB, not held in RAM).

## Fixed overhead you should plan for

### Schema catalog

Before streaming, PrivaCI introspects the source (`pg_class`, `pg_attribute`,
`pg_constraint`, etc.) and holds a typed in-memory catalog. This is
**metadata only** — column names, types, constraints — and is small compared
to row data even for schemas with hundreds of tables.

### Level 2 masking (SpaCy)

When freeform-text columns use local NER, the `en_core_web_sm` model is loaded
**once** at process start. Text for the current batch is passed through
`nlp.pipe()`; SpaCy does not load the whole table.

Disable Level 2 by using Level 1 actions only, or `action: passthrough` on
text columns, to avoid loading the model.

### Level 3 masking (commercial, opt-in)

`action: ai_refine` sends **context windows** to AWS Bedrock or Azure OpenAI.
The full column or table is never held in memory for L3; each window is
processed and discarded.

## Security: no intermediate data on disk

Masked values are never written to temporary files. All transformation happens
in-process between the two COPY streams. This is a deliberate security
constraint: PII must not land on container disk or shared volumes.

## Partitioned tables

Native PostgreSQL partitions are streamed as **independent units** (one child
partition at a time). The parent table holds no rows and is not streamed.
See [ADR-0009](../adr/0009-postgres-native-partitioning.md).

## Sizing a Kubernetes job or VM

Starting point for resource requests:

```yaml
# Helm values excerpt — adjust after a dry-run on your schema
resources:
  requests:
    memory: "1Gi"
    cpu: "2"
  limits:
    memory: "2Gi"
    cpu: "4"
```

Run `privaci dry-run` (when implemented) against your source to see table
widths and recommended batch sizes before sizing production jobs.

## Fallback: keyset pagination

If COPY-binary fails for a table (unsupported type, protocol edge case),
PrivaCI may fall back to **keyset pagination** (`WHERE pk > last_seen LIMIT n`)
with batched INSERTs. Throughput is lower (~10–20k rows/sec) but memory
remains bounded by the same batch-size rules. An audit-log entry records
the fallback. See [ADR-0006](../adr/0006-copy-binary-streaming.md).

## Implementation status

The memory model is **specified and ADR-approved**. Week-1 spike 2.1 validated
COPY-binary passthrough with `asyncpg`. The full streaming pipeline
(`privaci.stream`, tasks §12) is not yet implemented; integration tests will
assert bounded RSS on large/wide tables before public beta.

## See also

- [ADR-0006: COPY-binary streaming](../adr/0006-copy-binary-streaming.md)
- [ADR-0010: Constant-memory streaming bounds](../adr/0010-constant-memory-streaming.md)
- [Spike 2.1: COPY-binary round-trip](../spikes/2.1-copy-binary.md)
- OpenSpec: `openspec/changes/init-privaci-engine/specs/streaming-pipeline/spec.md`
