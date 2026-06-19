## ADDED Requirements

### Requirement: Optional `when` CEL guard on column actions

Each column action model SHALL accept an optional `when` field containing a
CEL expression. When omitted or empty, the action SHALL apply to every row
as today. When present, the action SHALL run only for rows where the
expression evaluates to `true`.

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

CEL compilation SHALL use column names and types from the catalog snapshot.
Supported value types in the row context SHALL be `null`, `bool`, `int`,
`double`, `string`, and `bytes`. The evaluator SHALL NOT perform database
I/O, filesystem access, network calls, or import arbitrary modules.
Expression length SHALL be capped at 512 characters; evaluation SHALL time
out at 5 ms per row per guarded column.

#### Scenario: Type mismatch caught at validation

- **WHEN** `when: "created_at > '2020-01-01'"` is applied to a `timestamptz`
  column typed as timestamp in catalog
- **THEN** validation SHALL either coerce per documented rules or exit `3`
  with a type error — never fail mid-run silently.

#### Scenario: Evaluation timeout

- **WHEN** a pathological expression exceeds the per-row timeout
- **THEN** the engine SHALL exit `1`, log the column path (not row values),
  and mark the run failed.

### Requirement: Growth+ tier for conditional masking

The engine SHALL require license tier `growth`, `business`, or `enterprise`
when any column action includes a non-empty `when` field. Starter and
community tiers SHALL exit `5` at config validation.

#### Scenario: Starter tier with `when`

- **WHEN** the license tier is `starter` and any column defines `when`
- **THEN** the engine SHALL exit `5` with tier-upgrade remediation.
