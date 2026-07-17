# schema-replication-modes

## Purpose

Define how `privaci run` handles target schema ownership: greenfield replication
(`replicate`) versus customer-managed prebuilt schemas (`assume_existing`), and the
tiered safety model for replicating non-table catalog objects.

## Requirements

### Requirement: Elevated object dispositions

An object SHALL be treated as **elevated** when it is a `SECURITY DEFINER`
function/procedure, or a view that does not use invoker rights (owner-privilege /
non-`security_invoker` view). Prefer the term **elevated** in docs and errors.

In `replicate` mode with view/function replication enabled, every detected elevated
object in scope SHALL have an explicit entry in `elevated_objects` with disposition
`replicate` or `skip`. The engine SHALL NOT auto-approve elevated objects during
`privaci init`.

#### Scenario: Unresolved elevated view fails preflight

- **WHEN** `schema_mode: replicate` and source has elevated view `clinical.admin_v`
  with no `elevated_objects` entry
- **THEN** preflight SHALL exit **2** naming the object
- **AND** SHALL NOT create the view on the target.

#### Scenario: Explicit skip continues without migrating

- **WHEN** `elevated_objects` contains `clinical.admin_v: skip`
- **THEN** the engine SHALL NOT create the view
- **AND** SHALL emit `skipped_object` with reason `elevated_object_skipped`
- **AND** the run SHALL continue for other objects.

#### Scenario: Explicit replicate creates elevated view

- **WHEN** `elevated_objects` contains `clinical.admin_v: replicate`
- **THEN** the engine SHALL create the view on the target
- **AND** SHALL emit `created_object` with `payload.kind = view` and an elevated marker
  in the payload.

#### Scenario: init surfaces elevated objects

- **WHEN** `privaci init` introspects a source that contains elevated objects
- **THEN** the scaffold SHALL include `elevated_objects: {}` (empty; no auto-approve)
- **AND** stdout SHALL list each elevated object as requiring a disposition.

### Requirement: Prebuilt schema validation in assume_existing mode

In `assume_existing` mode, preflight SHALL verify every in-scope config table exists
on the target with compatible column types matched by **name** (physical column order
SHALL NOT be required for compatibility) before any data write. On success the engine
SHALL write a `schema.validated` audit row when `audit_log` is enabled. On failure the
engine SHALL write a `schema.validation_failed` audit row when `audit_log` is enabled,
then exit **2**.

#### Scenario: Missing table fails preflight with audit

- **WHEN** `schema_mode: assume_existing` and `public.users` is in scope but absent
  on the target
- **THEN** preflight SHALL write `schema.validation_failed` naming the missing table
- **AND** SHALL exit **2**.

#### Scenario: Type mismatch fails preflight with audit

- **WHEN** source `public.users.email` is `text` but target column is `varchar(50)`
- **THEN** preflight SHALL write `schema.validation_failed` naming the column and both
  declared types
- **AND** SHALL exit **2**.

#### Scenario: Successful validation emits schema.validated

- **WHEN** `schema_mode: assume_existing` and all in-scope tables pass name+type checks
- **THEN** audit_log SHALL contain `schema.validated` with a tables-checked count
- **AND** the run SHALL proceed to load.

#### Scenario: Extra target columns do not fail compatibility

- **WHEN** the target table has all source columns by name+type plus an extra column
  at the end
- **THEN** assume_existing compatibility SHALL pass
- **AND** binary COPY eligibility for that table SHALL fail (see passthrough_copy).

### Requirement: Target collision policy under full-reload semantics

PrivaCI SHALL treat every load as a **full reload of source cell values**, including
primary-key and identity/`SERIAL` values, followed by sequence `setval` to the highest
streamed value for sequence-backed columns. The engine SHALL NOT treat absence of
auto-increment columns as permission to load into populated tables without truncate.

Under `on_existing_data: fail`:

- In `schema_mode: replicate`, preflight SHALL refuse when the target already has user
  tables outside `_privaci` (greenfield empty-database contract).
- In `schema_mode: assume_existing`, preflight SHALL refuse when any **in-scope** target
  table contains at least one row; empty prebuilt tables SHALL be allowed.
- The refusal SHALL be a hard preflight error (exit **2**), not a warning, and SHALL NOT
  depend on whether identity/`SERIAL` columns are present.

Under `on_existing_data: truncate`, the engine SHALL truncate in-scope tables before
streaming. `append` and assume_existing + `drop_create` remain rejected.

#### Scenario: assume_existing empty tables allowed with fail

- **WHEN** `schema_mode: assume_existing`, `on_existing_data: fail`, and every in-scope
  target table exists with zero rows
- **THEN** preflight SHALL NOT fail solely because the tables exist
- **AND** the run SHALL proceed to stream.

#### Scenario: assume_existing populated table fails without truncate

- **WHEN** `schema_mode: assume_existing`, `on_existing_data: fail`, and an in-scope
  target table contains rows
- **THEN** preflight SHALL exit **2** naming the collision policy
- **AND** SHALL remediate toward `on_existing_data: truncate`
- **AND** SHALL fail even when the table has no identity/`SERIAL` columns.

#### Scenario: truncate then load preserves explicit source keys

- **WHEN** `on_existing_data: truncate` and tables include identity/`SERIAL` columns
- **THEN** the engine SHALL truncate before load
- **AND** SHALL insert source key values explicitly
- **AND** SHALL `setval` sequence-backed columns to the streamed maximum after the table
  completes.

### Requirement: Tiered object replication in replicate mode

In `replicate` mode, non-table objects SHALL be handled in three tiers:

1. **Default-on:** functions/procedures, then plain views (dependency order), excluding
   elevated objects without an explicit disposition (see elevated-object requirement).
2. **Opt-in definition-only:** materialized views (`CREATE … WITH NO DATA`; never copy
   stored bytes; optional post-load `REFRESH`).
3. **Skipped:** triggers, rules, publications — `skipped_object` audit with reason.

DDL application order SHALL be: schemas → tables → indexes → foreign keys → functions
→ views → materialized view definitions → (stream rows) → optional matview refresh.

#### Scenario: Plain view replicated by default

- **WHEN** `schema_mode: replicate` and the source defines a non-elevated view
  `active_clinics_v`
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

### Requirement: passthrough_copy path selection

The top-level config SHALL accept `passthrough_copy`:

- `auto` (default) — use whole-table binary COPY when source and target column names,
  types, and physical order match; otherwise use the named batch path.
- `require_binary` — if any in-scope passthrough table is not binary-eligible, preflight
  SHALL exit **2** naming the table.
- `batch` — never use whole-table binary COPY; always use the named batch path.

Unexpected mid-run binary COPY errors SHALL fail the table/run; the engine SHALL NOT
silently switch paths mid-table.

#### Scenario: auto falls back when order differs

- **WHEN** `passthrough_copy: auto` and a passthrough table has matching names/types but
  different physical column order
- **THEN** the engine SHALL stream via the named batch path
- **AND** SHALL NOT fail preflight solely due to order.

#### Scenario: require_binary fails on order mismatch

- **WHEN** `passthrough_copy: require_binary` and a passthrough table is not
  binary-eligible
- **THEN** preflight SHALL exit **2** naming the table and the eligibility reason.
