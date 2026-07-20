## ADDED Requirements

### Requirement: Sidecar schema version

The public engine SHALL parse `pii-catalog.yaml` with `version: "1.0"` and a
`catalog` list. Each column entry SHALL include `sensitivity` in
`pii_direct` | `pii_indirect` | `internal` | `public`.

#### Scenario: Unknown sensitivity rejected

- **WHEN** sensitivity is not in the allowed enum
- **THEN** parse SHALL fail with exit **3**.

### Requirement: Import from PostgreSQL comments

`privaci catalog import-db-comments` SHALL emit a valid sidecar from source
column comments without reading row values.

#### Scenario: PII prefix

- **WHEN** comment is `PII: login email`
- **THEN** sensitivity SHALL be `pii_direct` and `source` SHALL be `pg_comment`.

#### Scenario: Empty comments

- **WHEN** no column comments exist
- **THEN** output SHALL be `version: "1.0"` and `catalog: []`.
