# schema-replication Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: DDL cloned from source to target

The system SHALL clone source DDL into the target database before any
rows are streamed. Cloning SHALL include schemas, tables, columns,
primary keys, unique constraints, foreign keys, check constraints, and
`NOT NULL` / default-expression annotations.

#### Scenario: Empty target, full clone

- **WHEN** the target is empty and the config does not override any
  table strategy
- **THEN** the engine SHALL create every in-scope schema and table in
  the target with DDL semantically equivalent to source.

#### Scenario: Schemas created idempotently

- **WHEN** a schema already exists in the target (e.g., from a prior
  run)
- **THEN** the engine SHALL issue `CREATE SCHEMA IF NOT EXISTS` and
  proceed.

#### Scenario: Reserved `_privaci` schema

- **WHEN** the target already contains the `_privaci` schema
- **THEN** the engine SHALL not consider it as "user data" during the
  target-empty pre-flight check.

### Requirement: Per-table strategy honored

For each table the system SHALL honor the configured strategy:

- `transform` (default) — clone DDL, stream and mask rows.
- `exclude` — do not create the table in target. **Pre-flight rejects
  this if any non-excluded table has an FK to the excluded one,
  unless that FK is nullable and the config also specifies
  `null_orphan_fks: true` on the referencing column.**
- `empty` — clone DDL, do not stream rows. Useful for tables whose
  contents are unsafe but whose schema is referenced.
- `truncate` — clone DDL only if it doesn't exist; otherwise truncate.
  (Engine treats this like `empty` from a row-loading perspective.)

#### Scenario: Strategy `exclude` with a dangling FK

- **WHEN** `audit_logs` is `exclude` and `users.last_audit_id` references
  it as a `NOT NULL` FK
- **THEN** the engine SHALL exit `3` at config validation with an error
  naming `users.last_audit_id` and suggest `strategy: empty` for
  `audit_logs`.

#### Scenario: Strategy `empty`

- **WHEN** `audit_logs` is `empty`
- **THEN** the engine SHALL create the `audit_logs` table in target with
  full DDL but SHALL NOT stream any rows into it.

#### Scenario: Strategy `transform` is the default

- **WHEN** a table appears in source but is not mentioned in config
- **THEN** the engine SHALL apply `transform` with auto-detect.

### Requirement: Partitioned tables replicated with parent + all partitions

The system SHALL replicate native (declarative) partitioned tables by
creating the partitioned parent first with the original `PARTITION
BY <strategy> (<keys>)` clause, then creating every partition child
with its original `PARTITION OF <parent> <bound>` clause.

Partitioned-table replication SHALL preserve:

- Partitioning strategy (`RANGE`, `LIST`, `HASH`).
- Partition key column list and order.
- Each partition's bound expression verbatim.
- Per-partition tablespace if specified (best-effort; falls back to
  default if the named tablespace is missing on target).

#### Scenario: Range-partitioned parent with 24 monthly children

- **WHEN** the source has `raw_events` partitioned monthly across 24
  partitions
- **THEN** the target SHALL have an identical parent + 24 partition
  children, each with the same bound, after replication.

#### Scenario: List-partitioned table

- **WHEN** the source has `clinical.patient_visits` partitioned by
  `LIST (region_code)` with four partitions
- **THEN** the target SHALL have the parent + four partitions with
  matching list bounds.

#### Scenario: Per-table strategy `exclude` on a partitioned parent

- **WHEN** the user sets `strategy: exclude` on the parent
- **THEN** the engine SHALL skip the parent and ALL partition
  children (no orphan partitions on target).

#### Scenario: Per-table strategy on an individual partition

- **WHEN** the user sets a strategy on a single partition child
  (e.g., `public.raw_events_2024_01`)
- **THEN** the engine SHALL exit `3` at config validation with the
  message: "Per-partition strategies are not supported; configure
  the partitioned parent instead."

### Requirement: Index replication is selective by default

The system SHALL replicate `UNIQUE` indexes (required for FK integrity
and for UNIQUE-aware faker behavior). Non-unique indexes SHALL NOT be
replicated by default, since staging databases rarely need the same
read-side index profile as production. A config flag
`replicate_all_indexes: true` SHALL allow opt-in full replication.

#### Scenario: Unique index present in source

- **WHEN** the source has `CREATE UNIQUE INDEX users_email_idx ON
  users(email)`
- **THEN** the engine SHALL create the same unique index on the target.

#### Scenario: Non-unique index, default config

- **WHEN** the source has `CREATE INDEX users_created_idx ON
  users(created_at)`
- **THEN** the engine SHALL NOT create the index on the target.

#### Scenario: Full-replication flag

- **WHEN** `replicate_all_indexes: true` is set
- **THEN** all source indexes SHALL be replicated.

### Requirement: Views, materialized views, triggers, rules are NOT replicated

In `schema_mode: replicate`, the system SHALL replicate **plain views** and
**functions/procedures** by default (see `schema-replication-modes`), except
**elevated** objects which require an explicit `elevated_objects` disposition.
Materialized views SHALL be replicated definition-only when
`replicate_materialized_views: true`. Triggers, rules, publications, subscriptions,
foreign-data-wrappers, event triggers, and permission grants SHALL remain skipped.

In `schema_mode: assume_existing`, the system SHALL NOT replicate any non-table object;
validation and load only.

The audit log SHALL record object disposition using `created_object`,
`definition_only_object`, or `skipped_object` as appropriate.

Sequences themselves ARE replicated where they back identity columns; the underlying
sequence object is not a skipped category.

#### Scenario: Source has a BEFORE INSERT trigger

- **WHEN** the source has triggers
- **THEN** the engine SHALL skip them and emit one `audit_log` entry per trigger with
  `event_type = 'skipped_object'`, `payload.kind = 'trigger'`, and a `reason`.

#### Scenario: Source has a plain view in replicate mode

- **WHEN** `schema_mode: replicate` and the source defines a non-elevated
  `CREATE VIEW active_clinics_v AS ...`
- **THEN** the engine SHALL create the view on the target after dependencies
- **AND** SHALL emit `created_object` with `payload.kind = 'view'`.

#### Scenario: Source has a materialized view with opt-in replication

- **WHEN** `replicate_materialized_views: true` and the source defines
  `CREATE MATERIALIZED VIEW tickets_open_mv AS ...`
- **THEN** the engine SHALL create the materialized view shell on the target with
  `WITH NO DATA`
- **AND** SHALL NOT copy source matview storage
- **AND** SHALL emit `definition_only_object` with `payload.kind = materialized_view`
  and `payload.contents_copied = false`.

#### Scenario: Source has a rule

- **WHEN** the source defines a `CREATE RULE` on any table
- **THEN** the engine SHALL skip the rule with a `skipped_object` audit entry.

#### Scenario: Elevated view without disposition is not replicated

- **WHEN** the source has an elevated view with no `elevated_objects` entry
- **THEN** the engine SHALL NOT create the view
- **AND** preflight SHALL fail naming the object.

### Requirement: Sequences replicated with adjusted current value

The system SHALL replicate both **legacy `SERIAL` / `BIGSERIAL`**
columns and **modern `GENERATED ... AS IDENTITY`** columns. The
backing sequence (whether an attached-sequence or an
identity-owned sequence) SHALL be created on the target and
`setval`-ed to one greater than the maximum value observed during
streaming, so application inserts after a masking run will not
collide with masked rows.

For `GENERATED ALWAYS AS IDENTITY` columns, the target column SHALL
also be created `GENERATED ALWAYS AS IDENTITY`, preserving the
"application cannot insert an explicit id" constraint that
production has.

For `GENERATED BY DEFAULT AS IDENTITY` columns, the same applies.

#### Scenario: Source `users.id` is legacy `SERIAL` with `max(id) = 1_000_000`

- **WHEN** streaming completes
- **THEN** the engine SHALL execute `SELECT setval('users_id_seq',
  1000000)` on the target.

#### Scenario: Source `patients.id` is `GENERATED ALWAYS AS IDENTITY`

- **WHEN** the catalog records the column as identity
- **THEN** the engine SHALL emit `GENERATED ALWAYS AS IDENTITY` in
  the target DDL and `setval` the identity-owned sequence to
  `max(id) + 1`.

#### Scenario: Empty source table

- **WHEN** source table is empty
- **THEN** the sequence SHALL be created with default starting value 1.

### Requirement: Idempotent index and foreign-key DDL

The engine SHALL make unique index and foreign-key creation idempotent when
replicating table DDL in `replicate` mode: re-applying the same replication on a
target that already has the objects SHALL NOT fail.

#### Scenario: Unique index already exists

- **WHEN** a unique index from the source already exists on the target
- **THEN** replication SHALL continue without error.

#### Scenario: Foreign key already exists

- **WHEN** a foreign key constraint from the source already exists on the target
- **THEN** replication SHALL continue without error.
