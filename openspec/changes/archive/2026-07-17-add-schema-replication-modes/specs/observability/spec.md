## ADDED Requirements

### Requirement: Object replication audit events

Structured logging and `_privaci.audit_log` SHALL support three object disposition
event types in addition to existing run events:

- `created_object` — DDL applied on target (`view`, `function`, etc.).
- `definition_only_object` — shell created without copying source bytes (materialized
  views); payload SHALL include `contents_copied: false`.
- `skipped_object` — intentionally not replicated; payload SHALL include `kind` and
  `reason`.

#### Scenario: Replicated view emits created_object

- **WHEN** a plain view is replicated in `schema_mode: replicate`
- **THEN** stdout and audit_log SHALL contain `created_object` with `schema_name`,
  `object_name`, and `payload.kind = view`.

#### Scenario: Materialized view emits definition_only_object

- **WHEN** a materialized view definition is replicated with `WITH NO DATA`
- **THEN** audit_log SHALL contain `definition_only_object` with
  `payload.contents_copied = false`.

#### Scenario: Trigger emits skipped_object with reason

- **WHEN** a trigger is skipped during replication
- **THEN** audit_log SHALL contain `skipped_object` with `payload.kind = trigger`
  and a non-empty `reason`.

### Requirement: Assume-existing schema validation audit events

Structured logging and `_privaci.audit_log` SHALL support:

- `schema.validated` — assume_existing name+type validation succeeded; payload SHALL
  include tables-checked count and the effective `passthrough_copy` mode.
- `schema.validation_failed` — assume_existing validation refused the load; payload
  SHALL name mismatched tables/columns and declared types without PII values.

Stdout SHALL continue to emit `preflight.ok` / `preflight.fail` for operators. When
`audit_log: false`, the engine SHALL skip writing these audit rows but SHALL still
emit stdout preflight events and exit codes.

#### Scenario: Successful assume_existing emits schema.validated

- **WHEN** `schema_mode: assume_existing` and validation succeeds with `audit_log: true`
- **THEN** audit_log SHALL contain `schema.validated`
- **AND** stdout SHALL contain `preflight.ok`.

#### Scenario: Failed assume_existing emits schema.validation_failed then exits

- **WHEN** `schema_mode: assume_existing` and a required table is missing with
  `audit_log: true`
- **THEN** audit_log SHALL contain `schema.validation_failed` naming the table
- **AND** stdout SHALL contain `preflight.fail`
- **AND** the process SHALL exit **2**.
