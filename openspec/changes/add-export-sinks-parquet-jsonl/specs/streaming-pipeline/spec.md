## ADDED Requirements

### Requirement: File sink formats (Business+ tier)

The streaming pipeline SHALL support writing masked rows to a configured
file sink with `format: jsonl` or `format: parquet`. Masking SHALL occur
in-process before any bytes are written. Unmasked row data SHALL NOT be
written to disk.

File sink configuration SHALL require a Business, Enterprise, or equivalent
 licensed tier. Starter and Growth SHALL exit `5` at config validation.

#### Scenario: JSONL masked export

- **WHEN** `sink: { type: file, format: jsonl, path: /out/users.jsonl }` is
  configured and `users` is streamed with email masking
- **THEN** each line SHALL be a JSON object with masked values and the file
  SHALL NOT contain original email substrings.

#### Scenario: Parquet schema fidelity

- **WHEN** a table with `int8`, `text`, `timestamptz`, and `uuid` columns is
  exported as Parquet
- **THEN** the Parquet schema SHALL preserve column names and logical types
  readable by `pyarrow.parquet.read_table`.

#### Scenario: Growth tier rejected

- **WHEN** the license tier is `growth` and a file sink is configured
- **THEN** the engine SHALL exit `5` at config validation.

### Requirement: Bounded-memory file encoding

File sinks SHALL accept rows in the same batch sizes as the DB streaming
path. Memory for buffering a batch SHALL NOT exceed the global batch byte
cap (256 MB default).

#### Scenario: Large table export

- **WHEN** exporting a 50 GB table with default batch size
- **THEN** RSS SHALL remain bounded per the streaming pipeline memory
  requirement.

### Requirement: Sink metadata in audit and run summary

On run completion, the engine SHALL record sink format, resolved path URI
(scheme only for remote — no credentials), tables exported, row counts, and
approximate bytes written in `_privaci.runs.summary`.

#### Scenario: Run summary includes sink stats

- **WHEN** a file sink run succeeds
- **THEN** `runs.summary` SHALL include `sink.format` and per-table row
  counts without row payloads.

### Requirement: Dual-write (Business+ tier)

The engine SHALL mask each row once and write to both a relational target
and a file sink within the same batch boundary when dual-write is configured.
Dual-write SHALL require Business or Enterprise tier.

#### Scenario: Single mask, dual destination

- **WHEN** dual-write is enabled for a batch of 10k rows
- **THEN** the masking pipeline SHALL invoke row transformation once per
  row and both destinations SHALL receive identical masked values.
