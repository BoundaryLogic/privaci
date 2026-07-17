## ADDED Requirements

### Requirement: Function and procedure introspection

The catalog SHALL introspect user-defined functions and procedures from
`pg_proc` / `pg_namespace`, recording schema name, object name, argument types,
return type, language, security (`SECURITY DEFINER` vs invoker), and the `CREATE`
statement text sufficient for replication.

Dependency edges to other functions and to in-scope tables SHALL be recorded for
topological ordering during DDL replication.

#### Scenario: View-calling function discovered

- **WHEN** `active_clinics_v` depends on function `clinical.fn_active_count()`
- **THEN** introspection SHALL return the function before the view in the
  replication dependency order.

#### Scenario: Function referencing excluded table fails preflight

- **WHEN** a replicated function body references a table with `strategy: exclude`
- **THEN** preflight SHALL exit **2** naming the function and the excluded dependency.

#### Scenario: SECURITY DEFINER function marked elevated

- **WHEN** a function is defined as `SECURITY DEFINER`
- **THEN** introspection SHALL mark it as elevated for disposition checks.

### Requirement: Elevated view detection

The catalog SHALL detect views that do not use invoker rights (owner-privilege /
non-`security_invoker`) and mark them as elevated for disposition checks.

#### Scenario: Non-invoker view marked elevated

- **WHEN** a plain view is defined without invoker rights
- **THEN** introspection SHALL mark it as elevated
- **AND** replication SHALL require an `elevated_objects` disposition before create.
