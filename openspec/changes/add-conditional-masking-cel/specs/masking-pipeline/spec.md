## ADDED Requirements

### Requirement: Per-row conditional action dispatch

Before executing a column's configured action, the masking pipeline SHALL
evaluate the optional `when` CEL expression against the current input row.
If the expression is absent or evaluates to `true`, the action SHALL run.
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

### Requirement: Conditional skip audit trail

When a `when` expression evaluates to `false`, the audit log SHALL record a
`conditional_skip` event with the table, column, and a hash of the CEL
source. It SHALL NOT record the row value or the boolean inputs.

#### Scenario: Audit on skip

- **WHEN** ten rows skip masking due to `when: "archived == true"`
- **THEN** the audit summary SHALL include a count of conditional skips for
  that column without PII in the payload.
