## ADDED Requirements

### Requirement: Trigger definitions for optional replication

When trigger replication may run (`schema_mode: replicate` and
`replicate_triggers` not false), catalog introspection SHALL load user triggers
with create definitions sufficient for post-data DDL (including
`pg_get_triggerdef`), excluding internal triggers (`tgisinternal`).

#### Scenario: User trigger introspected with definition

- **WHEN** the source has a non-internal trigger on an in-scope table
- **THEN** the catalog SHALL expose schema, table, trigger name, and a create
  definition string for that trigger.
