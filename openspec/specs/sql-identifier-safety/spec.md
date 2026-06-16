# sql-identifier-safety Specification

## Purpose
TBD - created by archiving change harden-review-findings. Update Purpose after archive.
## Requirements
### Requirement: Single mandatory identifier-quoting helper

The system SHALL provide one function that renders a PostgreSQL identifier safe
for inclusion in dynamically built SQL, and all dynamically built SQL that embeds
a schema, table, column, or primary-key name SHALL use it. The helper SHALL double
any embedded double-quote character (`"` → `""`) and SHALL reject identifiers
containing NUL or other control characters. No module SHALL embed an identifier in
SQL via naive `f'"{name}"'` interpolation.

#### Scenario: Identifier containing a double quote is escaped

- **WHEN** an identifier `ev"il` is rendered for SQL
- **THEN** the helper returns `"ev""il"` so the quoted token cannot be escaped

#### Scenario: Identifier containing a control character is rejected

- **WHEN** an identifier containing a NUL or control character is rendered
- **THEN** the helper raises an error and no SQL is executed with that identifier

#### Scenario: Destructive statements use the helper

- **WHEN** the engine emits `DROP SCHEMA`, `TRUNCATE`, `INSERT`, `SELECT`, or
  remediation SQL that names a schema/table/column from catalog introspection
- **THEN** every such identifier is produced by the quoting helper

### Requirement: Source and target identifiers are treated as untrusted

The system SHALL treat schema, table, and column names obtained from the source or
target database catalog as untrusted input and SHALL NOT assume they match a safe
character set.

#### Scenario: Hostile catalog identifier does not inject SQL

- **WHEN** the source database contains a table whose name includes SQL-significant
  characters and the engine streams or truncates it
- **THEN** the run either processes the table safely or fails with a clear error,
  and no unintended SQL is executed

