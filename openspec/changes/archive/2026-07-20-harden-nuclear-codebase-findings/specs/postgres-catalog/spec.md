## ADDED Requirements

### Requirement: Check constraint definitions preserve PG shape
Catalog introspection SHALL store check-constraint `definition` values in the
shape returned by `pg_get_constraintdef` so emitters can round-trip without
guessing.

#### Scenario: Introspected definition includes CHECK keyword
- **WHEN** a table with a CHECK constraint is introspected
- **THEN** `CheckConstraintInfo.definition` begins with `CHECK`

### Requirement: Snapshot persistence lives in state
Loading and persisting schema snapshots against `_privaci` SHALL be owned by
the state package; catalog may provide pure serialization without importing
run status types.
