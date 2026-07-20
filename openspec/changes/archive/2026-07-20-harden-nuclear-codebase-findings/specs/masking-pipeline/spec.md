## ADDED Requirements

### Requirement: Composite unique does not imply per-column uniqueness
Masking uniqueness handling SHALL apply only to single-column unique
constraints. Columns that participate only in a composite UNIQUE SHALL NOT each
receive independent uniqueness suffixing solely because of that composite.

#### Scenario: Two-column unique
- **WHEN** a table has UNIQUE(a,b) and both columns are masked with fake
- **THEN** the engine does not treat a and b as independently unique for
  suffixing purposes
