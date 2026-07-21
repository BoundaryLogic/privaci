## MODIFIED Requirements

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

When Level 2 (`ner_mask`) is the resolved action, the engine SHALL require a
loadable SpaCy model. It SHALL NOT return source text unchanged for non-empty
values when SpaCy is unavailable.

#### Scenario: Pure L1 path

- **WHEN** a column is configured `action: regex_mask, pattern: "^\d{3}-\d{2}-\d{4}$", replace: "000-00-0000"`
- **THEN** matching values SHALL be replaced and SpaCy SHALL NOT be
  invoked for that column.

#### Scenario: L1 then L2 fallthrough

- **WHEN** a text column has no L1 action but is auto-detected as a
  freeform-text column and SpaCy is available
- **THEN** SpaCy NER SHALL run, detected entities SHALL be replaced via
  the deterministic faker, and the audit log SHALL record per-entity
  counts.

#### Scenario: ner_mask without SpaCy at runtime

- **WHEN** `ner_mask` is applied to a non-empty cell and SpaCy is unavailable
- **THEN** the engine SHALL raise a masking failure (exit **1**) and SHALL NOT
  write the original cell value as a successful mask outcome

#### Scenario: L3 referenced but unavailable

- **WHEN** the config sets `action: ai_refine` on any column AND no
  commercial layer is installed
- **THEN** validation SHALL fail with exit **5** (plugin/capability gate)
