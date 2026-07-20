## MODIFIED Requirements

### Requirement: Index replication is selective by default

The system SHALL replicate `UNIQUE` indexes (required for FK integrity and for
UNIQUE-aware faker behavior) in the **pre-data** phase. Non-unique indexes SHALL
NOT be replicated by default, since staging databases rarely need the same
read-side index profile as production. A config flag `replicate_all_indexes: true`
SHALL allow opt-in full replication of non-unique indexes in the **post-data**
phase (after row streaming completes).

#### Scenario: Unique index present in source

- **WHEN** the source has `CREATE UNIQUE INDEX users_email_idx ON users(email)`
- **THEN** the engine SHALL create the same unique index on the target in
  **pre-data**.

#### Scenario: Non-unique index, default config

- **WHEN** the source has `CREATE INDEX users_created_idx ON users(created_at)`
- **THEN** the engine SHALL NOT create the index on the target.

#### Scenario: Full-replication flag applies non-unique indexes post-data

- **WHEN** `replicate_all_indexes: true` is set
- **THEN** all source non-unique indexes SHALL be replicated in **post-data**
- **AND** UNIQUE indexes SHALL still be created in **pre-data**.

### Requirement: Views, functions, and triggers replicate in post-data; rules stay skipped

In `schema_mode: replicate`, the system SHALL replicate **plain views** and
**functions/procedures** by default in the **post-data** phase (see
`schema-replication-modes` and `ddl-phases`), except **elevated** objects which
require an explicit `elevated_objects` disposition. Materialized views SHALL be
replicated definition-only in **post-data** when `replicate_materialized_views:
true`. Triggers SHALL be replicated in **post-data** when `replicate_triggers` is
true (default) and skipped when false. Rules, publications, subscriptions,
foreign-data-wrappers, event triggers, and permission grants SHALL remain skipped.

In `schema_mode: assume_existing`, the system SHALL NOT replicate any non-table
object; validation and load only.

The audit log SHALL record object disposition using `created_object`,
`definition_only_object`, or `skipped_object` as appropriate, including
`ddl_phase` when an object is created.

Sequences themselves ARE replicated where they back identity columns; the
underlying sequence object is not a skipped category.

#### Scenario: Source has a BEFORE INSERT trigger with default config

- **WHEN** the source has triggers and `replicate_triggers` is true (default)
- **THEN** the engine SHALL create them in **post-data** and emit one
  `created_object` audit entry per trigger with `payload.kind = 'trigger'`.

#### Scenario: Source has a BEFORE INSERT trigger with replicate_triggers false

- **WHEN** `replicate_triggers: false` and the source has triggers
- **THEN** the engine SHALL skip them and emit one `audit_log` entry per trigger
  with `event_type = 'skipped_object'`, `payload.kind = 'trigger'`, and a
  `reason`.

#### Scenario: Source has a plain view in replicate mode

- **WHEN** `schema_mode: replicate` and the source has a non-elevated plain view
- **THEN** the engine SHALL create the view on the target in **post-data** after
  dependencies
- **AND** SHALL emit `created_object` with `payload.kind = 'view'`.

#### Scenario: Source has a materialized view with opt-in replication

- **WHEN** `replicate_materialized_views: true` and the source defines a
  materialized view
- **THEN** the engine SHALL create the materialized view shell on the target with
  `WITH NO DATA` in **post-data**
- **AND** SHALL NOT copy source matview storage
- **AND** SHALL emit `definition_only_object` with `payload.kind = materialized_view`.

#### Scenario: Elevated view without disposition is not replicated

- **WHEN** the source has an elevated view with no `elevated_objects` entry
- **THEN** the engine SHALL NOT create the view
- **AND** SHALL fail preflight naming the object (see elevated-object requirements).
