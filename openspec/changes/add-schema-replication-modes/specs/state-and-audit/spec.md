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
