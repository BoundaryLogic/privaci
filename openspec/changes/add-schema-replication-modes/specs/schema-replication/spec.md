## MODIFIED Requirements

### Requirement: Views, materialized views, triggers, rules are NOT replicated

In `schema_mode: replicate`, the system SHALL replicate **plain views** and
**functions/procedures** by default (see `schema-replication-modes`). Materialized
views SHALL be replicated definition-only when `replicate_materialized_views: true`.
Triggers, rules, publications, subscriptions, foreign-data-wrappers, event triggers,
and permission grants SHALL remain skipped.

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

- **WHEN** `schema_mode: replicate` and the source defines
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

## ADDED Requirements

### Requirement: Idempotent index and foreign-key DDL

When replicating table DDL in `replicate` mode, unique index and foreign-key
creation SHALL be idempotent: re-applying the same replication on a target that
already has the objects SHALL NOT fail.

#### Scenario: Unique index already exists

- **WHEN** a unique index from the source already exists on the target
- **THEN** replication SHALL continue without error.

#### Scenario: Foreign key already exists

- **WHEN** a foreign key constraint from the source already exists on the target
- **THEN** replication SHALL continue without error.
