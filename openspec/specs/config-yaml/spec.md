# config-yaml Specification

## Purpose
TBD - created by archiving change harden-review-findings. Update Purpose after archive.
## Requirements
### Requirement: regex_mask patterns are guarded against catastrophic backtracking

The system SHALL protect against catastrophic backtracking (ReDoS) when applying a
user-supplied `regex_mask` pattern to cell values, either by bounding match time or
by rejecting patterns/inputs that would risk runaway evaluation. A pathological
pattern or value SHALL NOT be able to hang the masking pipeline indefinitely.

#### Scenario: Pathological pattern does not hang the run

- **WHEN** a `regex_mask` action uses a backtracking-prone pattern against a long
  adversarial value
- **THEN** the masking step is bounded and the run fails or continues rather than
  hanging indefinitely

### Requirement: Auto-detect substring rules avoid common false positives

Auto-detect substring matching SHALL NOT flag clearly non-PII columns as PII for
common short tokens. In particular, generic columns such as `company_name` SHALL NOT
be classified as credit-card data by a `pan` substring rule, and similar `tel`/`cell`
tokens SHALL be scoped to reduce false positives.

#### Scenario: company_name is not treated as a credit-card column

- **WHEN** auto-detect scans a column named `company_name`
- **THEN** it is not classified as a credit-card (PAN) column

### Requirement: Strict pydantic config model

The system SHALL parse `mask-rules.yaml` (or path supplied via `--config`)
into a strict pydantic model tree. The top-level model SHALL set
`model_config = ConfigDict(extra="forbid")` so unknown keys cause a
config-validation error. The model SHALL be exported as JSON Schema
via `privaci schema config` for IDE auto-completion support.

#### Scenario: Unknown top-level key

- **WHEN** the YAML contains `unknown_field: 1`
- **THEN** the engine SHALL exit `3` and the error SHALL name
  `unknown_field`.

#### Scenario: Typo in action name

- **WHEN** a column action is `regex_mas` (typo)
- **THEN** the engine SHALL exit `3` with a `pydantic` validation error
  listing the column path and the valid action names.

### Requirement: Version field is required

The top-level config SHALL require a `version` field. The MVP engine
SHALL accept `version: "1.0"` only.

#### Scenario: Missing version

- **WHEN** the YAML omits the `version` field
- **THEN** the engine SHALL exit `3` with an error directing the user
  to add `version: "1.0"`.

#### Scenario: Future-version config in MVP engine

- **WHEN** an MVP engine (v1.x) sees `version: "2.0"`
- **THEN** the engine SHALL exit `3` with the message: "Config version
  2.0 is not supported by engine v1.x. Pin engine to v2 or downgrade
  the config."

#### Scenario: Older-version config in a future engine

- **WHEN** a future engine (v2.x) sees `version: "1.0"`
- **THEN** the engine SHALL exit `3` with the message and command:
  `privaci migrate-config --from 1.0 --to 2.0 mask-rules.yaml`.

### Requirement: Config schema covers all MVP actions

The pydantic model SHALL include discriminated unions for action types:

- `fake` — `provider`, optional provider-specific params.
- `regex_mask` — `pattern` (regex), `replace` (string), optional `flags`.
- `hash` — no params.
- `passthrough` — no params.
- `null` — no params; rejected at validation if column is `NOT NULL`.
- `static` — `value` (string).
- `ner_mask` — optional `entities` filter (defaults to `[PERSON, ORG,
  GPE, LOC]`).
- `ai_refine` — `provider` (e.g., `aws_bedrock`), `model`, optional
  per-provider params. **Rejected at validation when the commercial
  layer is not installed.**

Each table entry SHALL have:

- `strategy`: `transform` (default) | `exclude` | `empty` | `truncate`.
- `columns`: mapping of column name → action.
- Optional `batch_size`, `null_orphan_fks`, `seed_alias`-on-column.

#### Scenario: Valid example from the proposal

- **WHEN** the YAML in the original product proposal (`users`, `customer_tickets`,
  `audit_logs`) is parsed
- **THEN** validation SHALL succeed, with `audit_logs` warning that
  `customer_tickets.agent_notes` uses `ai_refine` and therefore requires
  the commercial layer.

#### Scenario: `regex_mask` with invalid regex

- **WHEN** a `regex_mask` action specifies a non-compilable pattern
- **THEN** the engine SHALL exit `3` with the regex compile error.

### Requirement: Top-level options

The top-level config SHALL accept:

- `version` (required, string)
- `global_salt` (optional string or secret URI; resolved via
  `secrets-resolver`)
- `schema_mode`: `replicate` (default) | `assume_existing`
- `passthrough_copy`: `auto` (default) | `require_binary` | `batch`
- `on_existing_data`: `fail` (default) | `truncate` | `drop_create` |
  `append` (`append` SHALL fail validation in MVP).
- `replicate_views`: bool (default `true`; only in `replicate` mode)
- `replicate_functions`: bool (default `true`; only in `replicate` mode)
- `replicate_triggers`: bool (default `true`; only in `replicate` mode;
  when true, triggers are created in the **post-data** phase)
- `elevated_objects`: mapping of schema-qualified object name → `replicate` | `skip`
  (default empty; only meaningful in `replicate` mode when views/functions are enabled)
- `replicate_materialized_views`: bool (default `false`)
- `refresh_materialized_views`: bool (default `false`)
- `strict_autodetect`: bool (default `false`).
- `replicate_all_indexes`: bool (default `false`; non-unique indexes created in
  **post-data** when true).
- `batch_size`: int (default `10000`).
- `audit_log`: bool (default `true`).
- `auto_detect`: bool (default `true`).
- `tables`: mapping of table identifier → table config.

#### Scenario: `append` strategy in MVP

- **WHEN** `on_existing_data: append` is set
- **THEN** the engine SHALL exit `3` with the message "append strategy
  is not supported in this version. Use truncate or drop_create."

#### Scenario: assume_existing with truncate

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: truncate`
- **THEN** preflight SHALL truncate in-scope target tables and SHALL NOT emit DDL
  for tables, views, or functions.

#### Scenario: assume_existing fail allows empty prebuilt tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and in-scope
  target tables exist and are empty
- **THEN** preflight SHALL succeed without refusing the run solely for emptiness.

#### Scenario: assume_existing fail refuses populated tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and any in-scope
  target table contains at least one row
- **THEN** preflight SHALL exit `2`.

#### Scenario: assume_existing rejects drop_create

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: drop_create`
- **THEN** config validation SHALL exit `3`.

#### Scenario: replicate_triggers default is true

- **WHEN** `replicate_triggers` is omitted from config
- **THEN** the engine SHALL treat it as `true` in `schema_mode: replicate`.

### Requirement: Validation errors are actionable

Every config validation error SHALL include:

- The exact YAML path (`tables.users.columns.email.provider`).
- A description of the constraint that failed.
- A suggested fix where one is obvious.

#### Scenario: Missing required provider param

- **WHEN** a column uses `action: fake` but omits `provider`
- **THEN** the error message SHALL include
  `tables.users.columns.first_name: missing 'provider'. Try:
  provider: first_name`.

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
