# observability Specification

## Purpose
TBD - created by archiving change harden-review-findings. Update Purpose after archive.
## Requirements
### Requirement: Event redaction is safe-by-default

The event redaction layer SHALL redact value-bearing fields by default and SHALL
only emit a field's raw content when that field is explicitly classified as
structural/non-sensitive. Adding a new value-bearing event field SHALL NOT leak its
value merely because it was omitted from an allowlist.

#### Scenario: A new value-bearing field is redacted

- **WHEN** an event carries a value-bearing field that is not in the structural
  allowlist
- **THEN** its value is redacted rather than emitted raw

### Requirement: Value previews cannot reconstruct short PII

Any preview the system emits for a possibly-sensitive value SHALL NOT reveal enough
of the original to reconstruct short PII (for example a social-security number, name,
or short email local-part). Previews SHALL be non-reversible (for example a length
indicator plus a salted hash prefix) rather than the leading characters of the raw
value.

#### Scenario: SSN preview does not leak the number

- **WHEN** a value such as `123-45-6789` is previewed for a DEBUG log or event
- **THEN** the emitted preview does not contain the leading digits of the SSN

### Requirement: JSON-lines stdout event protocol

The system SHALL emit one JSON object per line to stdout for every
significant lifecycle event. Each line SHALL be a complete, valid JSON
object terminated by `\n`. Output SHALL NOT include color codes or
non-JSON decorations on stdout.

Every event SHALL include:

- `timestamp` (ISO-8601 UTC with microseconds)
- `level` (`debug`, `info`, `warning`, `error`)
- `event` (event-type identifier)
- `run_id` (uuid, after run.start)
- Event-specific fields (see below)

#### Scenario: Output is parseable line-by-line

- **WHEN** stdout is captured to a file `log.ndjson`
- **THEN** every non-empty line SHALL parse as a valid JSON object via
  `jq -c .` without errors.

#### Scenario: No ANSI color escapes on stdout

- **WHEN** stdout is captured
- **THEN** no ANSI escape sequences SHALL appear in the captured
  bytes.

### Requirement: Defined event-type catalog

The system SHALL emit the following events (and SHALL NOT use other
top-level event identifiers without a spec amendment):

- `run.start` — fields: `run_id`, `engine_version`, `config_hash`,
  `salt_fingerprint`, `source_db_hash`, `commercial_layer_present`
  (bool).
- `preflight.ok` / `preflight.fail` — fields: `checks` (array of
  `{name, status, detail}`).
- `schema.cloned` — fields: `tables_created`, `schemas_created`.
- `table.start` — fields: `schema_name`, `table_name`,
  `estimated_rows`.
- `table.progress` — fields: `schema_name`, `table_name`,
  `rows_processed`, `rows_per_sec`, `percent_complete`. Emitted at
  most once per 2 seconds per table.
- `table.end` — fields: `schema_name`, `table_name`, `rows_processed`,
  `duration_ms`, `status`.
- `column.masked` — fields: `schema_name`, `table_name`,
  `column_name`, `action`, `provider`, `rows_affected`.
- `cycle_break` — fields: `tables`, `deferred_constraint`.
- `polymorphic_fk_warning` — fields: `schema_name`, `table_name`,
  `type_column`, `id_column`.
- `implied_fk_warning` — fields: `source_column_path`,
  `inferred_target_column_path`, `suggested_seed_alias`.
- `skipped_object` — fields: `schema_name`, `object_name`,
  `kind` (`view`, `materialized_view`, `trigger`, `rule`, `publication`,
  `subscription`, `event_trigger`, `fdw`).
- `new_table` — fields: `schema_name`, `table_name`, `reason`
  (`new_partition` | `new_user_table`).
- `binary_fallback` — fields: `schema_name`, `table_name`,
  `unsupported_types`.
- `warning` — generic, with `message`.
- `error` — fields: `message`, `exit_code`.
- `run.end` — fields: `status`, `duration_ms`, `tables_processed`,
  `rows_processed`, `errors`.

#### Scenario: `table.progress` throttling

- **WHEN** a long-running table is streaming
- **THEN** `table.progress` events SHALL be emitted at most once every
  2 seconds for that table.

#### Scenario: Run lifecycle events

- **WHEN** a successful run completes
- **THEN** stdout SHALL contain exactly one `run.start` and one
  `run.end` with matching `run_id`.

### Requirement: stderr is reserved for unexpected errors

stdout SHALL be the canonical event channel. stderr SHALL be used only
for unexpected, uncaught exceptions where the structured logging
pipeline itself has failed (e.g., a stack trace from an unhandled
exception during startup).

#### Scenario: Expected error path

- **WHEN** pre-flight fails
- **THEN** the structured `preflight.fail` and `error` events SHALL go
  to stdout; stderr SHALL be empty.

#### Scenario: Catastrophic failure

- **WHEN** an unhandled exception occurs before structured logging is
  initialized
- **THEN** the stack trace MAY go to stderr.

### Requirement: PII redaction in events

No event payload SHALL contain raw column values. Any value-bearing
field (e.g., for debugging matches) SHALL be truncated to 8 chars and
prefixed with `***`.

#### Scenario: Audit-quality logs reveal no PII

- **WHEN** a third-party reads a captured stdout file
- **THEN** no PII values SHALL be present in any event payload.

### Requirement: Optional Prometheus `/metrics` endpoint

The system SHALL support an optional Prometheus exposition endpoint on a
configurable port that is off by default and opt-in via flag or config.
When enabled, the endpoint SHALL serve metrics including:

- `privaci_run_rows_processed_total` (counter, labels: table)
- `privaci_run_duration_seconds` (histogram)
- `privaci_run_errors_total` (counter, labels: type)
- `privaci_table_progress_ratio` (gauge, labels: table)

#### Scenario: Prometheus endpoint enabled

- **WHEN** `--prometheus-port 9100` is passed
- **THEN** the engine SHALL serve Prometheus exposition format on
  `:9100/metrics`.

#### Scenario: Default off

- **WHEN** no Prometheus flag is passed
- **THEN** no network ports SHALL be opened.

### Requirement: Log-level control

The system SHALL accept `--log-level <debug|info|warning|error>` and the
equivalent `PRIVACI_LOG_LEVEL` env var, defaulting to `info`. The
underlying `logging` module SHALL be configured via this setting.

#### Scenario: Debug level

- **WHEN** `--log-level debug` is passed
- **THEN** additional `debug` events SHALL appear on stdout.

