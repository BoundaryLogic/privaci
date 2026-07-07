# schema-replication-modes Specification

## Purpose

Define how `privaci run` handles target schema ownership: greenfield replication
(`replicate`) versus customer-managed prebuilt schemas (`assume_existing`), and the
tiered safety model for replicating non-table catalog objects.

## ADDED Requirements

### Requirement: Two schema modes

The top-level config SHALL accept `schema_mode`:

- `replicate` (default) — PrivaCI owns target DDL for in-scope objects within safe
  tiers, then streams masked rows.
- `assume_existing` — PrivaCI SHALL NOT create or alter table DDL; it SHALL validate
  the prebuilt target schema, apply `on_existing_data`, then stream masked rows.

#### Scenario: Default is replicate

- **WHEN** `schema_mode` is omitted from config
- **THEN** the engine SHALL behave as `schema_mode: replicate`.

#### Scenario: assume_existing skips DDL replication

- **WHEN** `schema_mode: assume_existing` is set
- **THEN** `replicate_schema` SHALL NOT be invoked
- **AND** masked rows SHALL still be streamed into existing in-scope tables.

### Requirement: Tiered object replication in replicate mode

In `replicate` mode, non-table objects SHALL be handled in three tiers:

1. **Default-on:** functions/procedures, then plain views (dependency order).
2. **Opt-in definition-only:** materialized views (`CREATE … WITH NO DATA`; never copy
   stored bytes; optional post-load `REFRESH`).
3. **Skipped:** triggers, rules, publications — `skipped_object` audit with reason.

DDL application order SHALL be: schemas → tables → indexes → foreign keys → functions
→ views → materialized view definitions → (stream rows) → optional matview refresh.

#### Scenario: Plain view replicated by default

- **WHEN** `schema_mode: replicate` and the source defines `active_clinics_v`
- **THEN** the engine SHALL create the view on the target after its dependencies
- **AND** SHALL emit `created_object` with `payload.kind = view`.

#### Scenario: Materialized view definition only

- **WHEN** `replicate_materialized_views: true` and the source defines
  `tickets_open_mv`
- **THEN** the engine SHALL create the materialized view with `WITH NO DATA`
- **AND** SHALL NOT copy stored rows from the source materialized view
- **AND** SHALL emit `definition_only_object` with `payload.contents_copied = false`.

#### Scenario: Trigger remains skipped

- **WHEN** the source has a `BEFORE INSERT` trigger
- **THEN** the engine SHALL NOT create the trigger on the target
- **AND** SHALL emit `skipped_object` with `payload.kind = trigger` and a documented
  `reason`.

### Requirement: Prebuilt schema validation in assume_existing mode

In `assume_existing` mode, preflight SHALL verify every in-scope config table exists
on the target with compatible column types before any data write.

#### Scenario: Missing table fails preflight

- **WHEN** `schema_mode: assume_existing` and `public.users` is in scope but absent
  on the target
- **THEN** preflight SHALL exit **3** naming the missing table.

#### Scenario: Type mismatch fails preflight

- **WHEN** source `public.users.email` is `text` but target column is `varchar(50)`
- **THEN** preflight SHALL exit **3** naming the column and both declared types.
