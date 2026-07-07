## ADDED Requirements

### Requirement: Function and procedure introspection

The catalog SHALL introspect user-defined functions and procedures from
`pg_proc` / `pg_namespace`, recording schema name, object name, argument types,
return type, language, and the `CREATE` statement text sufficient for replication.

Dependency edges to other functions and to in-scope tables SHALL be recorded for
topological ordering during DDL replication.

#### Scenario: View-calling function discovered

- **WHEN** `active_clinics_v` depends on function `clinical.fn_active_count()`
- **THEN** introspection SHALL return the function before the view in the
  replication dependency order.

#### Scenario: Function referencing excluded table fails preflight

- **WHEN** a replicated function body references a table with `strategy: exclude`
- **THEN** preflight SHALL exit **3** naming the function and the excluded dependency.
