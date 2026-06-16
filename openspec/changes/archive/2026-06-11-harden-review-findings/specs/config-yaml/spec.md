## ADDED Requirements

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
