## ADDED Requirements

### Requirement: `column.conditional_skip` audit event

Structured logging and `_privaci.audit_log` SHALL support
`column.conditional_skip` for rollup evidence that a CEL `when` guard skipped
masking for some rows. Payload SHALL include an expression hash and skip
counts and SHALL NOT include cell values.

#### Scenario: Event listed in operator docs

- **WHEN** conditional masking skips rows for a column
- **THEN** `docs/state-schema.md` and `docs/observability.md` SHALL document
  `column.conditional_skip`
- **AND** `EventType` in the public engine SHALL include the matching value.
