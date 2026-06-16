# postgres-catalog Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: Catalog introspection

The system SHALL introspect the source database using PostgreSQL system
catalogs (`pg_class`, `pg_attribute`, `pg_constraint`, `pg_namespace`,
`pg_index`, `pg_type`) to produce a typed in-memory representation of
the source schema. The introspection SHALL run in a single read-only
transaction and SHALL NOT modify any source data.

For each table the engine SHALL record:

- Schema name and table name.
- Ordered list of columns: name, declared type, `NOT NULL`, default
  expression, identity / generated status.
- Primary key columns (ordered).
- Unique constraints (ordered column lists).
- Foreign keys: source columns, referenced table, referenced columns,
  `ON DELETE` / `ON UPDATE` actions, `DEFERRABLE` flag, `INITIALLY
  DEFERRED` flag.
- Check constraints (recorded verbatim for replication).
- Indexes (recorded; only `UNIQUE` indexes are replicated to target by
  default).
- Estimated row count from `pg_class.reltuples`.

#### Scenario: Standard schema introspection

- **WHEN** the engine connects to a Postgres source containing a `users`
  table with a primary key, a unique email, and a foreign key to `orgs`
- **THEN** introspection SHALL return a `TableInfo` for `users`
  containing all those constraints and a reference to `orgs.id` in the
  FK list.

#### Scenario: Multi-schema source

- **WHEN** the source contains tables in `public`, `analytics`, and
  `auth` schemas
- **THEN** the engine SHALL include all three by default and SHALL
  preserve schema-qualified naming in `TableInfo`.

#### Scenario: Excluded system schemas

- **WHEN** introspection runs
- **THEN** the engine SHALL skip `pg_catalog`, `information_schema`,
  `pg_toast`, and any schema starting with `pg_`.

#### Scenario: Source permission insufficient

- **WHEN** the introspection role lacks `SELECT` on `pg_class`
- **THEN** introspection SHALL fail with a structured error naming the
  missing grant, and the engine SHALL exit `2`.

### Requirement: Foreign-key dependency graph and topological sort

The system SHALL build a directed graph of FK dependencies (edge from
referenced table → referencing table) and produce a load order via
topological sort. The output SHALL be a list of layers, where each
layer is a set of tables with no dependencies between them; layers are
loaded in order.

#### Scenario: Acyclic FK graph

- **WHEN** the catalog contains `orgs → users → orders → order_items`
  with no cycles
- **THEN** the topo sort SHALL produce layers `[orgs] → [users] →
  [orders] → [order_items]`.

#### Scenario: Self-referential FK

- **WHEN** a table has `employees.manager_id → employees.id`
- **THEN** the engine SHALL emit `employees` in a single layer with a
  `self_cycle: true` marker and load the table with
  `SET CONSTRAINTS ... DEFERRED`.

#### Scenario: Cyclic FK between two tables

- **WHEN** `orders.user_id → users.id` and `users.last_order_id →
  orders.id` both exist
- **THEN** the engine SHALL identify the cycle, select the lowest-cost
  edge to defer (preferring nullable FKs), emit a `cycle_break` audit
  event naming the deferred edge, and load both tables in a single
  transaction with `SET CONSTRAINTS ... DEFERRED`.

#### Scenario: FK is not `DEFERRABLE` but cycle requires deferral

- **WHEN** the engine needs to defer a non-`DEFERRABLE` constraint
- **THEN** the engine SHALL exit `2` at pre-flight with an error
  containing the exact SQL snippet needed to make the constraint
  `DEFERRABLE INITIALLY IMMEDIATE`.

### Requirement: Polymorphic-FK detection (limitation surface)

The system SHALL pattern-detect common polymorphic-FK conventions where
the catalog cannot model the relationship. Detected patterns SHALL emit
a `warning` event and an `audit_log` entry; they SHALL NOT block the
run.

Recognized patterns:

- `<x>_type` (string) and `<x>_id` (integer/uuid) appearing on the
  same table where `<x>_type` is not in any catalog FK.
- Columns named `commentable_*`, `subject_*`, `target_*`, `owner_*`
  with type + id pairing.

#### Scenario: Rails-style polymorphic association

- **WHEN** a `comments` table has columns `commentable_type` (text) and
  `commentable_id` (bigint) with no catalog FK
- **THEN** the engine SHALL emit one warning naming `comments` and
  describing the limitation, and the run SHALL continue.

### Requirement: Estimated row counts feed batching

`pg_class.reltuples` SHALL be used by the streaming layer to size
batches and progress bars. Tables with `reltuples = -1` (never analyzed)
SHALL trigger a `warning` event recommending `ANALYZE`.

#### Scenario: Never-analyzed source table

- **WHEN** any source table has `reltuples = -1`
- **THEN** the engine SHALL emit a warning and default to a conservative
  batch size of 1000 for that table.

### Requirement: Native partitioned tables are recognized

The system SHALL detect PostgreSQL native (declarative) partitioning
during introspection. For each partitioned-parent table the engine
SHALL record:

- `is_partitioned: true` on the parent's `TableInfo`.
- The partitioning strategy (`RANGE`, `LIST`, or `HASH`).
- The ordered partition-key column list.
- A list of partition children, each with its bound specification
  (the literal `FOR VALUES ...` clause).

For each partition child the engine SHALL record:

- `parent_partition: <parent-table-id>`.
- The bound expression as a string (for replication).
- All standard `TableInfo` fields (columns, PKs, FKs, etc.).

#### Scenario: Range-partitioned parent with monthly children

- **WHEN** the source has `raw_events` partitioned by `RANGE
  (event_at)` with twenty-four monthly partitions
- **THEN** introspection SHALL produce one `TableInfo` for the
  parent with `is_partitioned = true`, partitioning_strategy =
  `RANGE`, partition_key = `[event_at]`, and twenty-four
  `partition_child` entries each with its own `TableInfo` and a
  `bound: 'FOR VALUES FROM (...) TO (...)'` string.

#### Scenario: List-partitioned table

- **WHEN** the source has `patient_visits` partitioned by `LIST
  (region_code)` with four partitions
- **THEN** introspection SHALL produce the parent + four children,
  each with its `bound: 'FOR VALUES IN (...)'`.

#### Scenario: Sub-partitioning (out of MVP scope)

- **WHEN** the source has multi-level partitioning (a partition
  that is itself partitioned)
- **THEN** introspection SHALL detect it, emit a warning event,
  and exit `2` at pre-flight with the message "sub-partitioned
  tables are not supported in v1.0."

#### Scenario: Partition with foreign-key to non-partitioned table

- **WHEN** a partitioned table has FKs into normal tables
- **THEN** the FK SHALL appear once on the parent in the dependency
  graph (not duplicated per child), preserving topological-sort
  correctness.

### Requirement: Implied (soft) foreign-key detection

The system SHALL extend polymorphic-FK detection to also flag
**implied (soft) FKs** — column-name conventions that suggest an
informal cross-table reference where no catalog constraint exists.

Recognized patterns:

- A column named `<x>_email`, `<x>_username`, `<x>_user_id`, or
  `<x>_mrn` (and similar) on any table where another table in the
  source has a UNIQUE column matching the suffix.
- Free-text columns whose value distribution strongly overlaps a
  UNIQUE column elsewhere (deferred — out of MVP, captured for
  v1.x).

For each detected implied FK the engine SHALL emit one
`implied_fk_warning` event with the source column path and the
inferred target column path, and SHALL recommend a `seed_alias`
config entry in the warning message.

The detection SHALL NOT block the run. The user MAY explicitly
silence individual warnings via config:

```yaml
implied_fk_ignore:
  - clinical.patient_documents.referring_provider_email
```

#### Scenario: Soft email reference detected

- **WHEN** `clinical.patient_documents.referring_provider_email`
  exists and `clinical.providers.email` is UNIQUE
- **THEN** the engine SHALL emit one `implied_fk_warning` naming
  both columns and SHALL suggest:
  `seed_alias: clinical.providers.email`.

#### Scenario: Soft reference user explicitly silenced

- **WHEN** the column is listed under `implied_fk_ignore`
- **THEN** the engine SHALL NOT emit the warning.

#### Scenario: No matching UNIQUE target column

- **WHEN** a `*_email` column exists but no UNIQUE `email` column
  exists anywhere in the source
- **THEN** the engine SHALL NOT emit a warning.

### Requirement: Catalog snapshot persisted on the run

The system SHALL serialize the introspection result as canonical JSON
and persist it in `_privaci.runs.source_schema_snapshot` for the
current run. This snapshot SHALL be the basis of future drift detection
(commercial v1.x).

#### Scenario: Snapshot is deterministic

- **WHEN** introspection runs twice against an unchanged source
- **THEN** the canonical JSON outputs SHALL be byte-identical.

