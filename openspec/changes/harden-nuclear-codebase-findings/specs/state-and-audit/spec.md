## ADDED Requirements

### Requirement: Resume requires completed schema phase in replicate mode
When `schema_mode: replicate` and an incomplete run is resumed, the engine SHALL
refuse resume with exit code **2** if the persisted source schema snapshot is
absent, with remediation that cites `--force-restart` or a fresh target. When
the snapshot is present, resume SHALL re-run idempotent `replicate_schema`
before streaming.

#### Scenario: Resume without snapshot fails
- **WHEN** a run crashed during schema replication before snapshot persist and
  the operator resumes
- **THEN** the engine exits **2** and does not stream

#### Scenario: Resume with snapshot re-applies DDL
- **WHEN** a snapshot is present and the operator resumes in replicate mode
- **THEN** idempotent `replicate_schema` runs before table streaming

### Requirement: Force restart abandons incomplete runs
`privaci run --force-restart` SHALL abandon the incomplete target run and start
a fresh run when `on_existing_data` is `truncate` or `drop_create`. When
`on_existing_data` is `fail`, the engine SHALL refuse `--force-restart` at
preflight (exit **2**).

#### Scenario: Force restart with truncate
- **WHEN** an incomplete run exists and the operator passes `--force-restart`
  with `on_existing_data: truncate`
- **THEN** a new run starts and remediations that cite `--force-restart` are
  accurate

#### Scenario: Force restart rejected under fail policy
- **WHEN** the operator passes `--force-restart` with `on_existing_data: fail`
- **THEN** preflight exits **2** with remediation to set truncate or drop_create

### Requirement: Audit skipped_object always includes reason
Every `skipped_object` audit row and observability emit SHALL include a
`reason` string token.

#### Scenario: Flag-disabled matview skip
- **WHEN** a materialized view is skipped because replication is disabled
- **THEN** the audit payload includes `kind` and `reason`
