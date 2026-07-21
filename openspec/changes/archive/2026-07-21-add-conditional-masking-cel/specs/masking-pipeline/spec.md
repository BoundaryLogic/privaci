## ADDED Requirements

### Requirement: Per-row conditional action dispatch

Before executing a column's configured action, the masking pipeline SHALL
evaluate the optional `when` CEL expression against the current input row.
If the expression is absent or evaluates to CEL `true`, the action SHALL run.
If it evaluates to `false`, the pipeline SHALL leave the column value
unchanged and SHALL NOT invoke L1, L2, or auto-detect for that cell.

#### Scenario: L2 not invoked when `when` is false

- **WHEN** a text column has `action: ner_mask` with `when: "is_public == true"`
  and `is_public` is false for the row
- **THEN** SpaCy SHALL NOT run for that cell and the text SHALL be unchanged.

#### Scenario: Auto-detect does not override skipped cell

- **WHEN** auto-detect would mask a column but config sets a `when` that is
  false for the row
- **THEN** auto-detect SHALL NOT apply to that cell.

### Requirement: Conditional skip audit trail (rollup)

When a `when` expression evaluates to `false` for one or more rows in a
table, the audit log SHALL record at most one `column.conditional_skip`
event per guarded column for that table stream, with payload fields
`expression_hash`, `skipped_rows`, and `evaluated_rows` (or equivalent
documented names). It SHALL NOT write one audit row per skipped cell and
SHALL NOT record row values or predicate inputs.

#### Scenario: Audit on skip

- **WHEN** ten rows skip masking due to `when: "archived == true"` on column
  `notes`
- **THEN** audit_log SHALL contain one `column.conditional_skip` for `notes`
  with `skipped_rows = 10` and no PII in the payload.

### Requirement: Binary path respects conditional masking

Streaming eligibility SHALL treat any table with a non-empty column `when`
as ineligible for whole-table binary COPY (same class of exclusion as
non-passthrough actions).

#### Scenario: Mixed when forces batch path

- **WHEN** `passthrough_copy: auto` and only some rows would mask under `when`
- **THEN** the engine SHALL still stream the table via the batch path
- **AND** SHALL evaluate `when` per row.
