## ADDED Requirements

### Requirement: pg_dump-style DDL phases in replicate mode

In `schema_mode: replicate`, the engine SHALL apply catalog DDL in three named
phases aligned with PostgreSQL dump sections:

1. **pre-data** — structure required before row inserts.
2. **data** — masked/passthrough row streaming.
3. **post-data** — secondary structure and side-effecting objects after rows load.

#### Scenario: Phase names appear in docs and audits

- **WHEN** an object is created during replication
- **THEN** operator docs SHALL describe it as belonging to `pre-data` or `post-data`
- **AND** the corresponding audit event payload SHALL include
  `ddl_phase` of `pre-data` or `post-data`.

### Requirement: Pre-data object membership

The **pre-data** phase SHALL create, in dependency-safe order: schemas, required
extensions, sequences used by identity/serial columns, tables, partition children,
PRIMARY KEY and UNIQUE indexes (including unique indexes that are not foreign-key
targets), and foreign keys. The engine SHALL NOT create non-unique indexes,
triggers, plain views, functions/procedures, or materialized-view shells in
pre-data.

#### Scenario: Unique index before first row

- **WHEN** the source has a UNIQUE index on `users(email)` and a run starts
- **THEN** the engine SHALL create that unique index in **pre-data**
- **AND** SHALL begin streaming only after pre-data for in-scope tables completes.

#### Scenario: Non-unique index not in pre-data

- **WHEN** `replicate_all_indexes: true` and the source has a non-unique index
- **THEN** the engine SHALL NOT create that index during pre-data
- **AND** SHALL create it during post-data after streaming completes.

### Requirement: Post-data object membership

The **post-data** phase SHALL run only after in-scope table streaming has
completed successfully (or all tables are already `done` on resume), and SHALL
complete successfully before the run is marked `SUCCEEDED`. Post-data failure
SHALL fail the run (not leave a successful run with incomplete schema).

Post-data SHALL apply, when configured: non-unique indexes (`replicate_all_indexes`),
functions/procedures not required in pre-data (see pre-data function hoist),
plain views, optional materialized-view shells, triggers (when `replicate_triggers`
is true), and optional materialized-view refresh. Per-table sequence `setval`
SHALL remain part of the **data** phase (after each table load), not post-data.

#### Scenario: Views appear after streaming

- **WHEN** `replicate_views: true` and the source defines a non-elevated view
- **THEN** the engine SHALL create the view in **post-data**
- **AND** SHALL NOT create it before streaming completes.

#### Scenario: Post-data failure prevents SUCCEEDED

- **WHEN** post-data DDL fails after all tables have streamed
- **THEN** the engine SHALL NOT mark the run `SUCCEEDED`
- **AND** SHALL surface an actionable error naming the failing object without PII.

### Requirement: Pre-data functions for DEFAULT and CHECK dependencies

When a table column `DEFAULT` or `CHECK` expression depends on a user function,
that function SHALL be created in **pre-data** (subject to `elevated_objects`)
before the table DDL is applied. Remaining in-scope functions SHALL be created
in **post-data** before views and triggers that depend on them.

#### Scenario: DEFAULT referencing a function

- **WHEN** `public.users` has `DEFAULT public.gen_token()` and `gen_token` is
  in scope and non-elevated (or explicitly `replicate`)
- **THEN** the engine SHALL create `gen_token` in **pre-data** before
  `CREATE TABLE public.users`.

### Requirement: Trigger catalog sufficient to emit DDL

The catalog SHALL expose enough trigger metadata to emit create statements in
post-data (schema, table, name, and create definition from `pg_get_triggerdef`
or equivalent). Internal triggers SHALL remain excluded. Name-only skip records
are insufficient for `replicate_triggers: true`.

#### Scenario: Trigger definition available when replication enabled

- **WHEN** `replicate_triggers` is true and the source has a user trigger
- **THEN** catalog introspection SHALL provide a create definition for that
  trigger
- **AND** post-data SHALL apply it after dependent functions exist.

### Requirement: Trigger replication in post-data

When `replicate_triggers` is `true` (default), the engine SHALL create in-scope
source triggers on the target during **post-data**, after their dependent
functions exist, and SHALL emit `created_object` with `payload.kind = trigger`
and `ddl_phase = post-data`. When `replicate_triggers` is `false`, the engine
SHALL NOT create triggers and SHALL emit `skipped_object` with
`payload.kind = trigger` and a documented reason.

Elevated functions used by triggers remain subject to `elevated_objects`
dispositions. Rules, publications, subscriptions, FDWs, event triggers, and
permission grants SHALL remain skipped.

#### Scenario: Default replicates trigger after load

- **WHEN** `replicate_triggers` is omitted or `true` and the source has a
  `BEFORE INSERT` trigger on an in-scope table
- **THEN** the engine SHALL create the trigger in post-data
- **AND** SHALL NOT fire that trigger against rows inserted during the data phase.

#### Scenario: Opt-out skips trigger

- **WHEN** `replicate_triggers: false`
- **THEN** the engine SHALL NOT create the trigger
- **AND** SHALL emit `skipped_object` with `payload.kind = trigger`.
