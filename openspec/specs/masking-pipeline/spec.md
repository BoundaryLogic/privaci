# masking-pipeline Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: Three-tier masking pipeline, Levels 1 and 2 in public engine

The system SHALL apply masking actions in a defined order, per column:

- **Level 1 — Deterministic rules** (regex match / replace, type-based
  defaults, hash, deterministic faker invocation).
- **Level 2 — Local NER** (SpaCy `en_core_web_sm`) for `PERSON`, `ORG`,
  `GPE`, `LOC` entities in free-text columns.
- **Level 3 — BYO-LLM** — defined as an extension contract; the public
  engine SHALL NOT ship a default implementation.

A column's resolved action SHALL come from one of (in priority order):

1. Explicit per-column config in `mask-rules.yaml`.
2. Auto-detect rule (see `auto-detect`).
3. The fall-through default: passthrough.

#### Scenario: Pure L1 path

- **WHEN** a column is configured `action: regex_mask, pattern: "^\d{3}-\d{2}-\d{4}$", replace: "000-00-0000"`
- **THEN** matching values SHALL be replaced and SpaCy SHALL NOT be
  invoked for that column.

#### Scenario: L1 then L2 fallthrough

- **WHEN** a text column has no L1 action but is auto-detected as a
  freeform-text column
- **THEN** SpaCy NER SHALL run, detected entities SHALL be replaced via
  the deterministic faker, and the audit log SHALL record per-entity
  counts.

#### Scenario: L3 referenced but unavailable

- **WHEN** the config sets `action: ai_refine` on any column AND no
  commercial layer is installed
- **THEN** the engine SHALL exit `3` at config validation with the
  message "Level 3 connectors require the commercial layer."

### Requirement: Masking is a pure function of (config, salt, row)

The system SHALL implement masking as pure functions over `(table_config,
salt, input_row) → output_row`. No masking function SHALL perform I/O.
All randomness, including SpaCy model invocation, SHALL be derived
deterministically from the salt.

#### Scenario: Same input, same salt → same output (no I/O)

- **WHEN** the same row is processed twice with the same salt and
  config
- **THEN** the output SHALL be byte-identical, with no network or disk
  activity originating from the masking layer.

#### Scenario: SpaCy entity replacement is deterministic

- **WHEN** SpaCy detects the entity "John Smith" twice in different rows
  with the same salt
- **THEN** the replacement value SHALL be identical in both rows.

### Requirement: Null and empty handling preserves source semantics

The system SHALL pass through `NULL` values unchanged. Empty strings
SHALL be passed through unless the action explicitly handles them.

#### Scenario: NULL email column

- **WHEN** a row has `email = NULL`
- **THEN** the output row SHALL have `email = NULL`, regardless of any
  configured email action.

#### Scenario: Empty string

- **WHEN** a column action is `fake` and the input is `""`
- **THEN** the output SHALL be `""`, not a fake value.

### Requirement: Column-level passthrough override

The system SHALL accept `action: passthrough` on any column and SHALL
bypass every masking level (including auto-detect) for that column.

#### Scenario: Auto-detect overridden

- **WHEN** auto-detect would mask `users.email` but the config sets
  `users.email: { action: passthrough }`
- **THEN** the email column SHALL appear unchanged in the target.

### Requirement: Action catalog

The public engine SHALL implement these L1 actions:

- `fake` — deterministic faker (see `deterministic-faker`).
- `regex_mask` — regex match-and-replace.
- `hash` — SHA-256(salt || value), hex-encoded.
- `passthrough` — copy unchanged.
- `null` — write NULL (rejected at config validation if column is `NOT NULL`).
- `static` — replace with a configured constant.

L2 (`ner_mask`) and L3 (`ai_refine`) SHALL be exposed as actions, with
L3 raising a config-validation error in the public engine.

#### Scenario: Configured hash

- **WHEN** a column is `action: hash`
- **THEN** the output SHALL equal `hex(sha256(salt || value))`.

#### Scenario: `action: null` on NOT NULL column

- **WHEN** a column is `NOT NULL` and config sets `action: null`
- **THEN** the engine SHALL exit `3` at config validation with the
  offending table+column.

### Requirement: Level 3 extension contract

The public engine SHALL define `privaci.contracts.LLMConnector` as an
`abc.ABC` with at least the following methods:

- `name(self) -> str`
- `redact_entities(self, text: str, *, salt: str, context: ColumnContext) -> RedactionResult`

The contract module SHALL be importable from the public engine. The
public engine SHALL provide a `NoOpLLMConnector` that raises
`L3NotInstalledError` when invoked, used to validate config in the
absence of the commercial layer.

#### Scenario: Contract is importable

- **WHEN** a Python program runs `from privaci.contracts import LLMConnector`
- **THEN** the import SHALL succeed regardless of whether the commercial
  layer is installed.

#### Scenario: NoOpLLMConnector raises on invocation

- **WHEN** `NoOpLLMConnector().redact_entities(...)` is called
- **THEN** the engine SHALL raise `L3NotInstalledError` with a message
  pointing to the commercial-layer installation docs.

### Requirement: PII never logged

The masking pipeline SHALL never log raw input or output values at any
level above DEBUG. At DEBUG, values SHALL be truncated to 8 characters
and surrounded by markers indicating they are sensitive.

#### Scenario: ERROR log during masking

- **WHEN** a masking function raises an exception with a column value
  in scope
- **THEN** the logged error message SHALL NOT contain the value, only
  the column path and the exception class.

