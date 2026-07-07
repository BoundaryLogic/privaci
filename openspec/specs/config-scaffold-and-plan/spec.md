# config-scaffold-and-plan Specification

## Purpose
TBD - created by archiving change add-config-scaffold-and-plan. Update Purpose after archive.
## Requirements
### Requirement: Init scaffolds mask-rules from source schema

The CLI SHALL provide `privaci init` that connects to the **source** database read-only,
introspects schema, applies auto-detect rules, and writes a starter `mask-rules.yaml`.

#### Scenario: Generate starter config

- **WHEN** a user runs `privaci init --source <dsn> --output mask-rules.yaml`
- **THEN** the engine SHALL write a valid config file with `version: "1.0"`
- **AND** `global_salt` SHALL reference `${ANONYMIZATION_SALT}` (not an inline secret)
- **AND** `auto_detect` SHALL default to `true` and `strict_autodetect` to `false`
- **AND** high-confidence auto-detect findings SHALL appear as column actions in YAML

#### Scenario: Source only — no target required

- **WHEN** `privaci init` runs
- **THEN** it SHALL NOT require `TARGET_DB_URL` or a target connection

#### Scenario: Refuse clobber without force

- **WHEN** `--output` path already exists and `--force` is not set
- **THEN** the command SHALL exit **2** without modifying the file

#### Scenario: Review reminder

- **WHEN** init succeeds
- **THEN** stdout SHALL summarize uncertain columns for human review
- **AND** the generated file SHALL include a header comment that manual review is required
  before production `run`

### Requirement: Plan previews masking without target

The CLI SHALL provide `privaci plan` that loads config, connects to **source** read-only,
merges config with auto-detect, and prints a masking plan without writing to a target.

#### Scenario: Source-only plan

- **WHEN** a user runs `privaci plan --config mask-rules.yaml`
- **THEN** the command SHALL NOT require `TARGET_DB_URL`
- **AND** it SHALL NOT write masked data or modify the target database

#### Scenario: Human-readable output

- **WHEN** `--format text` (default)
- **THEN** output SHALL list each table with strategy, estimated row count when available,
  and per-column mask or review lines consistent with dry-run summary style

#### Scenario: JSON output for CI

- **WHEN** `--format json`
- **THEN** output SHALL be a single JSON document with tables, columns, actions, confidence,
  and summary counts suitable for CI gates

#### Scenario: No PII in plan output

- **WHEN** plan or init emits logs or stdout
- **THEN** raw PII values from source rows SHALL NOT appear

### Requirement: Dry-run unchanged

`privaci dry-run` SHALL retain current behavior: source **and** target preflight, no
target writes.

#### Scenario: Plan is not a replacement for dry-run

- **WHEN** documentation describes the recommended flow
- **THEN** it SHALL position `plan` before target exists and `dry-run` after target is wired

