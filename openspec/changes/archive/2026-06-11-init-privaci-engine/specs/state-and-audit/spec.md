## ADDED Requirements

### Requirement: `_privaci` schema created idempotently on target

The system SHALL create a dedicated `_privaci` schema in the target
database on first run. The schema SHALL contain at least three tables:
`runs`, `table_checkpoints`, and `audit_log`. Subsequent runs SHALL
detect the existing schema and apply additive migrations (no
destructive changes) when needed.

#### Scenario: First run on a clean target

- **WHEN** the engine runs against a target that has no `_privaci`
  schema
- **THEN** the engine SHALL create `_privaci` and its tables before
  any user-data writes.

#### Scenario: Existing schema, compatible

- **WHEN** `_privaci` exists with the same engine-version schema
- **THEN** the engine SHALL proceed without modifications.

#### Scenario: Existing schema, incompatible

- **WHEN** `_privaci` exists with a future engine-version schema
- **THEN** the engine SHALL exit `2` with the message "target was
  initialized by a newer engine; pin to the matching version or run
  migrations."

#### Scenario: Permission denied

- **WHEN** the target role lacks `CREATE SCHEMA`
- **THEN** the engine SHALL exit `2` with an error message naming the
  required grant.

### Requirement: `_privaci.runs` schema

`_privaci.runs` SHALL include at minimum these columns:

- `run_id` (UUIDv7, primary key)
- `started_at` (timestamptz, default `now()`)
- `ended_at` (timestamptz, nullable)
- `status` (enum: `in_progress`, `succeeded`, `failed`, `interrupted`)
- `engine_version` (text)
- `config_hash` (text, sha256 of canonicalized config JSON)
- `salt_fingerprint` (text, sha256(salt)[:16] — never the salt itself)
- `source_db_hash` (text, sha256("<host>:<port>/<dbname>"))
- `source_schema_snapshot` (jsonb, the catalog snapshot)
- `summary` (jsonb, aggregate counts at run end)

#### Scenario: Run starts

- **WHEN** the engine begins streaming
- **THEN** exactly one row SHALL be inserted with status
  `in_progress`.

#### Scenario: Run completes

- **WHEN** all tables finish without error
- **THEN** the `runs` row SHALL be updated to `status = 'succeeded'`,
  `ended_at = now()`, and `summary` populated.

#### Scenario: Run is interrupted

- **WHEN** the engine receives SIGINT
- **THEN** before exiting it SHALL update the `runs` row to `status =
  'interrupted'` with a populated `ended_at`.

### Requirement: `_privaci.table_checkpoints` schema

`_privaci.table_checkpoints` SHALL include at minimum:

- `run_id` (uuid, FK to `runs.run_id`)
- `schema_name` (text)
- `table_name` (text)
- `status` (enum: `pending`, `in_progress`, `done`, `failed`)
- `last_pk_value` (text, nullable — null for tables without a usable
  monotonic PK)
- `rows_processed` (bigint, default 0)
- `last_update_at` (timestamptz, default `now()`)
- PRIMARY KEY (`run_id`, `schema_name`, `table_name`)

#### Scenario: Batch commit updates checkpoint

- **WHEN** a streaming batch of 10,000 rows commits
- **THEN** the corresponding `table_checkpoints` row SHALL update
  `last_pk_value`, increment `rows_processed`, and set `last_update_at`
  — all within the same transaction as the data write.

#### Scenario: Table completes

- **WHEN** the last batch of a table commits
- **THEN** the engine SHALL set `status = 'done'` for that table.

#### Scenario: Resume reads checkpoint

- **WHEN** `privaci resume` is invoked
- **THEN** the engine SHALL load the most recent `in_progress` run for
  the same (`source_db_hash`, `config_hash`) and SHALL start each
  not-`done` table from `last_pk_value`.

#### Scenario: Partitioned tables checkpoint per partition child

- **WHEN** a partitioned parent has N partition children
- **THEN** `_privaci.table_checkpoints` SHALL contain one row per
  partition child (each addressed by its fully qualified name) so
  resume granularity is per-partition, not per-parent.

### Requirement: `_privaci.audit_log` schema

`_privaci.audit_log` SHALL include at minimum:

- `audit_id` (uuid, primary key)
- `run_id` (uuid, FK to `runs.run_id`)
- `event_at` (timestamptz, default `now()`)
- `level` (enum: `info`, `warning`, `error`)
- `event_type` (text: e.g., `column.masked`, `column.passed_through`,
  `column.pii_detected`, `cycle_break`, `polymorphic_fk_warning`,
  `binary_fallback`, `strict_mode_violation`)
- `schema_name`, `table_name`, `column_name` (text, all nullable)
- `payload` (jsonb)

#### Scenario: Column masked

- **WHEN** a column is masked
- **THEN** one `audit_log` row SHALL be written with `event_type =
  'column.masked'` and `payload = { action, provider, rows_affected }`.

#### Scenario: Auto-detect PII finding

- **WHEN** auto-detect identifies a PII column not in config
- **THEN** a `column.pii_detected` audit row SHALL be written naming
  the column and matched pattern.

#### Scenario: Audit table opt-out

- **WHEN** the config has `audit_log: false` or CLI passes
  `--no-audit-table`
- **THEN** the engine SHALL skip writing to `audit_log` but SHALL still
  populate `runs` (for resumability).

### Requirement: Resumability prerequisites

The system SHALL allow resuming a run if and only if:

1. A run with `status = 'in_progress'` exists in `_privaci.runs`.
2. That run's `config_hash` matches the current config.
3. That run's `source_db_hash` matches the current source.
4. That run's `salt_fingerprint` matches the current salt's fingerprint.
5. `privaci resume` is explicitly invoked (no automatic resume on
   `run` to avoid accidental state reuse).

If any condition fails, the engine SHALL exit `2` with a structured
message indicating which condition failed.

#### Scenario: Config drift between attempts

- **WHEN** the user runs `privaci resume` after changing the YAML
- **THEN** the engine SHALL exit `2` with the message "config has
  changed since the last run; use `privaci run --force-restart` to
  start a fresh run."

#### Scenario: Source rotation

- **WHEN** the source DB URL changed
- **THEN** the engine SHALL exit `2` for the same reason.

#### Scenario: Salt rotation

- **WHEN** the salt fingerprint changed
- **THEN** the engine SHALL exit `2`; the user must either restore the
  old salt or start a fresh run.

### Requirement: Source-DB-hash is stable and emitted

The system SHALL emit `source_db_hash` as a field in stdout JSON-lines
events and persist it on each `_privaci.runs` row. The hash SHALL be
stable for a given source database (host, port, database name) so that
resumability and downstream aggregation can rely on it. How any
commercial layer aggregates these hashes is out of scope for the engine.

#### Scenario: Two runs against the same source

- **WHEN** the engine runs twice against the same source DB URL
- **THEN** the two `runs` rows SHALL have identical `source_db_hash`.

#### Scenario: Same host, different database name

- **WHEN** two runs target the same Postgres host but different
  databases (e.g., `prod_main` vs `prod_analytics`)
- **THEN** the two `runs` rows SHALL have different `source_db_hash`.
