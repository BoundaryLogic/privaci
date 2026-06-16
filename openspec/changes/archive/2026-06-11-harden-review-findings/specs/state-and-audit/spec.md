## ADDED Requirements

### Requirement: Resume gate matches all resumable finalized runs

The resume gate SHALL locate a resumable run whose status is `in_progress`,
`interrupted`, or `failed` (in addition to matching config hash, source-DB hash,
and salt fingerprint). A run finalized as `interrupted` after SIGINT/SIGTERM, or as
`failed` after a caught error, SHALL be discoverable by `privaci resume`. On
resume, the run SHALL be reset to `in_progress` in the same transaction that loads
its checkpoints.

#### Scenario: Resume after a graceful interrupt

- **WHEN** a run is interrupted by SIGINT and finalized with status `interrupted`
- **AND** the user invokes `privaci resume` with the same config, source, and salt
- **THEN** the gate finds that run and resumes it from its checkpoints

#### Scenario: Resume after a caught failure

- **WHEN** a run is finalized with status `failed`
- **AND** the user invokes `privaci resume` with matching identity
- **THEN** the gate finds that run rather than reporting "no run matches"

### Requirement: Resume gate reports which condition failed

When no resumable run is found, the system SHALL distinguish "no prior run exists"
from "a prior run exists but its config, source, or salt drifted", so the operator
learns which prerequisite failed.

#### Scenario: Salt drift is reported distinctly

- **WHEN** a resumable run exists for the identity but the salt fingerprint differs
- **THEN** the error states that the salt changed, not merely that no run was found

### Requirement: Checkpoint cursor parsing covers all single-column PK types

The system SHALL parse a stored checkpoint cursor into the correct type for every
supported single-column primary key, including integer, numeric, floating-point,
`uuid`, date/time, and boolean types, so resume queries (`WHERE pk > $1`) compare
correctly.

#### Scenario: UUID primary key resumes correctly

- **WHEN** a table with a `uuid` primary key is resumed
- **THEN** the stored cursor is parsed as a UUID and the resume query returns the
  next rows rather than failing or rescanning from the start

### Requirement: Resume validates source-schema-snapshot drift

On resume, the system SHALL compare the current source catalog against the
`source_schema_snapshot` recorded for the run and SHALL fail with a structured
pre-flight error when the source schema has drifted.

#### Scenario: Source schema changed during the interruption

- **WHEN** a column is added or removed on the source between interruption and
  resume
- **THEN** resume fails loudly with a drift error instead of resuming against a
  changed schema

### Requirement: Checkpoint completion fails loud on zero-row updates

When marking a table checkpoint done, the system SHALL verify a row was updated and
SHALL raise a state error if no checkpoint row matched, rather than silently
no-op'ing.

#### Scenario: Missing checkpoint row is detected

- **WHEN** `mark_table_done` targets a checkpoint that does not exist
- **THEN** the system raises a state error rather than reporting success
