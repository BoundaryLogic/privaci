## ADDED Requirements

### Requirement: Optional `when` CEL guard on column actions

Each column action model SHALL accept an optional `when` field containing a
CEL expression. When omitted or empty, the action SHALL apply to every row
as today. When present, the action SHALL run only for rows where the
expression evaluates to CEL `true`.

#### Scenario: Conditional mask applies

- **WHEN** `columns.notes` is `{ action: fake, provider: lorem, when: "status == 'closed'" }`
  and a row has `status = 'closed'`
- **THEN** `notes` SHALL be masked per the `fake` action.

#### Scenario: Conditional mask skipped

- **WHEN** the same rule applies and a row has `status = 'open'`
- **THEN** `notes` SHALL pass through unchanged.

#### Scenario: Invalid CEL at validation

- **WHEN** `when` references `unknown_field`
- **THEN** the engine SHALL exit `3` naming `tables.<t>.columns.<c>.when`.

### Requirement: CEL environment is catalog-typed and sandboxed

CEL compilation SHALL use column names and types from the catalog snapshot
for the owning table. Supported CEL bindings SHALL follow the documented
PostgreSQL→CEL map (bool/int/double/string/bytes/null; timestamps as ISO
strings; `numeric` and jsonb/arrays/composites fail type-check with exit `3`
when referenced). The evaluator SHALL NOT perform database I/O, filesystem
access, network calls, or import arbitrary modules. Expression length SHALL
be capped at 512 characters; evaluation SHALL enforce a 5 ms deadline per
row per guarded column.

#### Scenario: Unsupported type referenced

- **WHEN** `when` references a `jsonb` column
- **THEN** catalog type-check SHALL exit `3` naming the column path.

#### Scenario: Evaluation timeout

- **WHEN** a pathological expression exceeds the per-row deadline
- **THEN** the engine SHALL exit `1`, log the column path (not row values),
  and mark the run failed.

### Requirement: Non-bool `when` result fails the run

A `when` expression SHALL evaluate to a CEL boolean. A non-bool result or
CEL runtime error SHALL fail the run with exit `1` and SHALL NOT treat the
value as false.

#### Scenario: String result rejected

- **WHEN** `when: "status"` evaluates to a string for a row
- **THEN** the engine SHALL exit `1` naming `tables.<t>.columns.<c>.when`.

### Requirement: Two-phase `when` validation

Config load SHALL enforce the `conditional_masking` capability and CEL
syntax/size limits without requiring a catalog. Catalog-aware type-check
SHALL run at preflight (and at `validate` when a catalog is available).

#### Scenario: Capability checked before catalog

- **WHEN** config contains `when` and capabilities omit `conditional_masking`
- **THEN** the engine SHALL exit `5` at config load without needing a database.

### Requirement: `conditional_masking` capability for `when` guards

The engine SHALL require the capability token `conditional_masking` in
`LicenseStatus.capabilities` when any column action includes a non-empty
`when` field. It SHALL NOT decide access by matching `LicenseStatus.tier`
against product tier names. Community mode (empty capabilities) and any
validator that omits the token SHALL exit `5` at config validation.

Public remediation text SHALL name the capability token and plugin/license
install path — not product tier names (ADR-0007).

#### Scenario: Capability present with `when`

- **WHEN** any column defines `when` and `conditional_masking` is in
  `LicenseStatus.capabilities`
- **THEN** config validation SHALL proceed past the capability gate.

#### Scenario: Capability missing with `when`

- **WHEN** any column defines `when` and `conditional_masking` is not in
  `LicenseStatus.capabilities`
- **THEN** the engine SHALL exit `5`.

### Requirement: Tables with `when` are not binary-COPY eligible

Any table that configures a non-empty `when` on at least one column action
SHALL use the row/batch masking path. Whole-table binary COPY SHALL NOT be
used for that table. When `passthrough_copy: require_binary` and any such
table is in scope, preflight SHALL exit `2` naming the table.

#### Scenario: require_binary rejects when

- **WHEN** `passthrough_copy: require_binary` and `users.email` has a `when`
- **THEN** preflight SHALL exit `2`.
