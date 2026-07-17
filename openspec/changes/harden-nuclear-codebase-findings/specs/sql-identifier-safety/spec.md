## ADDED Requirements

### Requirement: Non-table identifiers are validated
Before executing dynamic DDL for views, functions, sequences, indexes, or
named constraints, the engine SHALL validate those identifiers with the same
safety rules as table/column identifiers.

#### Scenario: Unsafe view name rejected
- **WHEN** introspection returns a view name containing disallowed characters
- **THEN** preflight fails before DDL execution
