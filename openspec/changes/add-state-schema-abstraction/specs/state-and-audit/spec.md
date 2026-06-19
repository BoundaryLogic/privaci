## ADDED Requirements

### Requirement: State access via `StateBackend`

All reads and writes to run state, checkpoints, and audit logs SHALL go
through a `StateBackend` implementation selected for the target database
dialect. Direct SQL for `_privaci` tables SHALL NOT be invoked from the
streaming pipeline or CLI except inside backend implementations.

#### Scenario: Postgres default backend

- **WHEN** `TARGET_DB_URL` uses a `postgresql://` or `postgres://` scheme
- **THEN** the engine SHALL use the built-in Postgres state backend and
  behavior SHALL match pre-abstraction semantics.

#### Scenario: Schema bootstrap idempotency

- **WHEN** `ensure_schema()` is called on a target that already has a
  compatible `_privaci` schema
- **THEN** the backend SHALL not destroy data and SHALL apply only additive
  migrations if needed.

### Requirement: Logical `_privaci` schema metadata

The system SHALL define `_privaci.runs`, `_privaci.table_checkpoints`, and
`_privaci.audit_log` as backend-neutral logical schemas. Each
`StateBackend` SHALL emit dialect-appropriate DDL and map logical types
(JSON, UUID, timestamptz, bigint, text enums) to native types.

#### Scenario: Column parity on Postgres

- **WHEN** the Postgres backend creates `_privaci` on a clean target
- **THEN** the resulting columns SHALL satisfy all requirements in the
  existing `state-and-audit` capability (run_id, status enums, jsonb
  payloads, etc.).

#### Scenario: Future-version rejection unchanged

- **WHEN** `_privaci.schema_metadata` reports a newer engine version than
  supported
- **THEN** the backend SHALL surface exit `2` with the same remediation
  text as today.

### Requirement: Catalog access via `CatalogBackend`

The pipeline SHALL perform schema discovery, FK graph construction,
topological sort, and partition metadata through a `CatalogBackend` bound
to the source connection. The pipeline SHALL NOT import PostgreSQL-specific
catalog queries directly.

#### Scenario: Discovery parity

- **WHEN** the Postgres catalog backend runs against the Demo Corp fixture
- **THEN** the discovered table graph SHALL match the current
  `postgres-catalog` integration baseline.
