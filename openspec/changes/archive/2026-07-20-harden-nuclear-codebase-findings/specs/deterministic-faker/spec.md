## ADDED Requirements

### Requirement: Faker uniqueness aligns with single-column uniques
Deterministic faker uniqueness suffixing SHALL follow the masking-pipeline rule
for single-column unique constraints only (see masking-pipeline composite
unique requirement).

#### Scenario: Single-column unique still unique
- **WHEN** a column has a single-column UNIQUE and is faked
- **THEN** collisions are still avoided via the existing uniqueness mechanism
