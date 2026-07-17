## ADDED Requirements

### Requirement: Object disposition audit rows

`_privaci.audit_log` SHALL accept `event_type` values `created_object` and
`definition_only_object` in addition to `skipped_object`. The `payload` jsonb
column SHALL carry `kind`, and when applicable `contents_copied`, `reason`, and
`depends_on`.

#### Scenario: created_object row shape

- **WHEN** a view is replicated
- **THEN** one audit row SHALL be written with `event_type = 'created_object'`,
  `schema_name` and `table_name` (object name) set, and `payload.kind = 'view'`.

#### Scenario: definition_only_object proves no byte copy

- **WHEN** a materialized view shell is created
- **THEN** one audit row SHALL be written with `event_type = 'definition_only_object'`
  and `payload.contents_copied = false`.

### Requirement: Schema validation audit rows

`_privaci.audit_log` SHALL accept `event_type` values `schema.validated` and
`schema.validation_failed`. These rows are the durable paper trail for
`assume_existing` preflight. Failure rows SHALL be written on the target connection
before the process exits when `audit_log` is enabled.

#### Scenario: schema.validated row on success

- **WHEN** assume_existing validation succeeds
- **THEN** one audit row SHALL be written with `event_type = 'schema.validated'`
  and a payload that includes the number of tables checked.

#### Scenario: schema.validation_failed row on refusal

- **WHEN** assume_existing validation fails because a column type mismatches
- **THEN** one audit row SHALL be written with `event_type = 'schema.validation_failed'`
  naming the table, column, and declared types
- **AND** the payload SHALL NOT contain cell values or other PII.
