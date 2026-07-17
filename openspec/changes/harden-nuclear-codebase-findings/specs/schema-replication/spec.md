## ADDED Requirements

### Requirement: CHECK constraints round-trip from introspection
When replicating tables, the engine SHALL emit CHECK (and other) constraints
using `pg_get_constraintdef` output without wrapping an additional `CHECK (...)`
around a definition that already includes the constraint type keyword.

#### Scenario: Live CHECK constraint on source
- **WHEN** the source table has a PostgreSQL CHECK constraint and
  `schema_mode: replicate`
- **THEN** target DDL succeeds and the constraint exists on the target

### Requirement: Foreign keys to excluded tables are not created
The engine SHALL NOT emit `REFERENCES` DDL to tables that are excluded or were
not created on the target.

#### Scenario: Child FK to excluded parent
- **WHEN** config excludes a parent table and a child has an FK to that parent
- **THEN** schema replication omits that foreign key on the target

### Requirement: null_orphan_fks nulls referencing columns when enabled
When `null_orphan_fks: true` and a nullable FK references an excluded table, the
engine SHALL set that FK column to NULL during streaming for loaded rows. Tables
subject to orphan nulling SHALL NOT use whole-table binary COPY; if
`passthrough_copy: require_binary` would otherwise apply, preflight SHALL fail.

#### Scenario: Nullable orphan FK with flag true
- **WHEN** `null_orphan_fks: true`, parent is excluded, child FK column is
  nullable, and a row is streamed
- **THEN** the child FK column is NULL on the target

#### Scenario: require_binary conflicts with orphan nulling
- **WHEN** `null_orphan_fks: true` applies to a table and
  `passthrough_copy: require_binary`
- **THEN** preflight fails with remediation to use `auto` or `batch`

### Requirement: drop_create preserves _privaci
When `on_existing_data: drop_create`, the engine SHALL NOT drop the `_privaci`
schema.

#### Scenario: drop_create leaves audit schema
- **WHEN** an operator runs with `drop_create` on a target that has `_privaci`
- **THEN** `_privaci` remains after schema reset
