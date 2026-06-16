# streaming-pipeline Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: Source-to-target streaming via COPY binary

The system SHALL stream each in-scope table from source to target using
PostgreSQL `COPY ... TO STDOUT (FORMAT BINARY)` on the source side and
`COPY ... FROM STDIN (FORMAT BINARY)` on the target side. In-process,
each row SHALL be decoded, passed through the masking pipeline, then
re-encoded for the target COPY. Source and target COPY operations SHALL
run concurrently in a single asyncio event loop.

#### Scenario: Round-trip preservation when no masking is configured

- **WHEN** a table is streamed end-to-end with no mask rules applied
- **THEN** the row count and per-column values in the target SHALL match
  the source byte-for-byte (modulo column-default and identity values).

#### Scenario: Memory remains bounded

- **WHEN** streaming a 100 GB table
- **THEN** RSS SHALL remain bounded by `batch_size * row_size + a small
  constant overhead`; the engine SHALL NOT load the full table into
  memory.

#### Scenario: Backpressure between source and target

- **WHEN** the target is slower than the source
- **THEN** the engine SHALL apply backpressure such that the source
  COPY pauses rather than buffering unbounded rows.

### Requirement: Batch sizing and tuning

The system SHALL stream rows in batches. Default batch size SHALL be
10,000 rows. The engine SHALL auto-tune `batch_size` downward when:

- Row width exceeds a heuristic threshold (default: total batch bytes
  cap of 256 MB).
- The streaming engine observes target-side queue blocking beyond a
  threshold.

Users MAY override `batch_size` per-table or globally in config.

#### Scenario: Wide-row auto-tune

- **WHEN** a table's average row width is ~50 KB
- **THEN** the engine SHALL reduce that table's batch size to keep the
  in-memory batch ≤ 256 MB.

#### Scenario: User override

- **WHEN** the user configures `tables.events.batch_size: 50000`
- **THEN** the engine SHALL use 50,000 rows for `events`, ignoring
  auto-tune unless memory thresholds are hit.

### Requirement: Per-batch checkpoint commits

For each successfully streamed batch, the system SHALL atomically:

1. Write the masked rows to the target via the in-flight COPY.
2. Persist the last primary-key value to `_privaci.table_checkpoints`
   for the current run and table.

The two writes SHALL be in the same transaction so that a crash leaves
the target consistent with the checkpoint.

#### Scenario: Crash between batches

- **WHEN** the engine crashes after committing batch N but before
  starting batch N+1
- **THEN** on resume the engine SHALL re-stream starting from the
  recorded `last_pk_value`; no rows SHALL be duplicated and no rows
  SHALL be skipped.

#### Scenario: Composite or non-monotonic primary keys

- **WHEN** a table's primary key is composite or non-monotonic
- **THEN** the engine SHALL fall back to table-level checkpoints (table
  done / not done) and SHALL record the fallback in the audit log.

### Requirement: FK cycle handling at load time

The system SHALL load all tables identified as part of a cycle (see
`postgres-catalog`) within a single transaction with `SET CONSTRAINTS
ALL DEFERRED`. Per-batch checkpoint commits for cyclic tables SHALL be
tracked, but constraint validation SHALL be deferred until the
enclosing transaction commits.

#### Scenario: Cycle commit succeeds

- **WHEN** all tables in a cycle finish streaming
- **THEN** the engine SHALL commit the deferred-constraint transaction
  and confirm constraint validity, then mark all involved tables as
  `done` in `_privaci.table_checkpoints`.

#### Scenario: Cycle commit fails on constraint check

- **WHEN** the deferred-constraint commit raises an FK violation
- **THEN** the engine SHALL roll back the entire cycle, mark the run as
  failed with a structured error naming the offending constraint, and
  exit `1`.

### Requirement: Type-fidelity binary codec

The system SHALL implement a binary COPY codec covering at minimum the
following PostgreSQL types: `bool`, `int2`, `int4`, `int8`, `float4`,
`float8`, `numeric`, `text`, `varchar`, `char`, `bytea`, `uuid`, `date`,
`time`, `timestamp`, `timestamptz`, `interval`, `json`, `jsonb`,
`inet`, `cidr`, `macaddr`, `enum`, and array variants of the above.

Types not covered (PostGIS, custom domains, user-defined types) SHALL
trigger a per-table fallback to text-mode COPY with a recorded warning.

#### Scenario: Unsupported type fallback

- **WHEN** a table contains a PostGIS `geometry` column
- **THEN** the engine SHALL stream that table in text COPY mode and
  record a `binary_fallback` audit event with the type name.

#### Scenario: All supported types round-trip

- **WHEN** a table contains all supported types
- **THEN** the engine SHALL stream in binary mode and the target rows
  SHALL byte-match the source rows when no masking is applied.

### Requirement: Partitioned tables streamed per-partition

The system SHALL stream each partition child as its own streaming
unit, not the partitioned parent. Streaming per-child enables
per-partition checkpointing (since each partition has its own
primary-key range) and lets the topo-sort schedule independent
partitions concurrently in the future.

For each partition child:

1. The child is treated as a distinct table for streaming purposes.
2. Its checkpoint row in `_privaci.table_checkpoints` uses the
   child's fully-qualified name.
3. The masking pipeline applies the **parent**'s configured per-
   column rules (because partitions inherit the parent's columns).
4. The target-side write uses `COPY <child> FROM STDIN ...`
   directly into the child (not via the parent's tuple routing).

#### Scenario: 24-partition table resumes after crash mid-partition-12

- **WHEN** the engine crashes while streaming
  `raw_events_2024_12`, after partitions 1-11 have completed and
  some batches of 12 have committed
- **THEN** on resume the engine SHALL leave partitions 1-11
  untouched, restart partition 12 from its `last_pk_value`, and
  proceed with 13-24.

#### Scenario: Partition-level config inheritance

- **WHEN** the parent table's config sets
  `columns.event_payload: { action: passthrough }`
- **THEN** the same rule SHALL apply when streaming each partition
  child.

#### Scenario: Adding a partition between runs

- **WHEN** a 25th partition is added to the source between two
  runs of the same configured masking job
- **THEN** the engine SHALL include the new partition in the next
  run automatically (it is a newly-seen table), and the audit log
  SHALL emit a `new_table` event naming it.

### Requirement: Connection handling

The system SHALL open exactly one source connection and one target
connection per concurrent table being streamed (MVP: serial table
streaming, so two total connections). Connections SHALL be opened via
context managers and SHALL be closed even on exception.

#### Scenario: Mid-run exception

- **WHEN** any exception occurs mid-stream
- **THEN** both DB connections SHALL be closed within the `finally`
  block before the exception propagates.

#### Scenario: Connection lost mid-stream

- **WHEN** the source connection drops mid-stream
- **THEN** the engine SHALL retry the current batch up to 3 times with
  exponential backoff. If all retries fail, the engine SHALL exit `1`
  with the underlying error.

