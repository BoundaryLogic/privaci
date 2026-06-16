## ADDED Requirements

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
- `on_existing_data`: `fail` (default) | `truncate` | `drop_create` |
  `append` (`append` SHALL fail validation in MVP).
- `strict_autodetect`: bool (default `false`).
- `replicate_all_indexes`: bool (default `false`).
- `batch_size`: int (default `10000`).
- `audit_log`: bool (default `true`).
- `auto_detect`: bool (default `true`).
- `tables`: mapping of table identifier → table config.

#### Scenario: `append` strategy in MVP

- **WHEN** `on_existing_data: append` is set
- **THEN** the engine SHALL exit `3` with the message "append strategy
  is not supported in this version. Use truncate or drop_create."

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
