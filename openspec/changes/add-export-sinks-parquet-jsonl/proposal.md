## Why

Some teams need masked datasets as files — Parquet for analytics lakes, JSONL
for downstream ETL — without provisioning a second relational target. Today the
streaming pipeline terminates only in PostgreSQL `COPY ... FROM STDIN`. Business
tier customers want same-engine masked export: one container run, constant
memory, audit trail intact.

## What Changes

- **File sink destinations** — config declares `sink: file` with `format:
  parquet | jsonl`, output path (local or URI resolved later by S3 change).
- **Same masking path** — rows flow source DB → masker → sink encoder; no
  unmasked spill to disk.
- **Parquet writer** — column types from catalog; chunked row groups aligned
  with streaming batch size.
- **JSONL writer** — one JSON object per line; UTF-8; stable key ordering for
  diff-friendly output.
- **Tier gating:** Business+ required; Growth/starter exit `5`.
- **Audit** — run summary records sink URI, format, row counts, byte size
  estimate; no row payloads.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `streaming-pipeline`: Optional file sink alongside or instead of DB target
  write leg; bounded-memory encode path.

## Impact

- **Code:** `src/privaci/stream/sinks/` (Parquet, JSONL), config top-level
  `sink` block, runner dispatch when target is file-only mode.
- **Dependencies:** `pyarrow` (Parquet); stdlib/json for JSONL.
- **Docs:** `docs/configuration.md`, deployment notes for ephemeral disk.
- **Tests:** Round-trip schema fidelity, memory cap, tier gate.
