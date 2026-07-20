## Why

Schema replication today applies nearly all DDL (including secondary indexes)
before streaming rows, and permanently skips triggers. That slows large loads
and leaves targets without trigger behavior operators expect after a mask run.
We need an explicit **pre-data / data / post-data** model (pg_dump-shaped) so
every object type has one clear phase, with post-data reserved for expensive or
side-effecting DDL.

## What Changes

- Formalize DDL into **pre-data**, **data** (row stream), and **post-data**
  phases under `schema_mode: replicate` (docs + pipeline + audit).
- **Pre-data:** schemas, extensions, sequences, tables, partition children,
  PRIMARY KEY / UNIQUE indexes (including unique indexes that are not FK
  targets), foreign keys, and any other structure required to insert safely
  (ADR-0008 unchanged: FKs stay during load).
- **Post-data:** secondary (non-unique) indexes; triggers (default **on**,
  configurable off); remaining functions/views/matview shells; matview REFRESH.
  Functions required by column DEFAULT/CHECK stay in **pre-data**. Per-table
  `setval` stays in the **data** phase (unchanged).
- Expand trigger catalog beyond name-only skips (`TriggerInfo` /
  `pg_get_triggerdef`) so post-data can emit DDL.
- **BREAKING (behavior):** secondary indexes and views/functions that previously
  appeared before the first row write will appear after streaming completes.
  Resume / mid-run target inspection may see tables without secondary indexes
  or views until post-data finishes.
- **BREAKING (behavior):** triggers are no longer always skipped; default is to
  create them in post-data (`replicate_triggers`, default `true`), with opt-out.
- Rules and publications remain skipped (unchanged) unless a later change says
  otherwise.
- `schema_mode: assume_existing` unchanged: customer owns all DDL phases.

## Capabilities

### New Capabilities

- `ddl-phases`: pg_dump-style pre-data / data / post-data ownership of catalog
  objects during `schema_mode: replicate`, including config knobs and audit
  markers for which phase created an object.

### Modified Capabilities

- `schema-replication-modes`: Replace the single “DDL then stream then optional
  matview refresh” order with the phased model; change triggers from always
  skipped to post-data replication (configurable).
- `schema-replication`: Align index timing and trigger skip requirements with
  phases (delta against the living capability).
- `config-yaml`: Add `replicate_triggers` (default `true`) and document phase
  semantics for index/view/function timing.
- `observability`: Audit events distinguish pre-data vs post-data object
  creation; trigger `created_object` instead of only `skipped_object`.
- `postgres-catalog`: First-class trigger introspection (`TriggerInfo` /
  `pg_get_triggerdef`) sufficient to emit post-data DDL.

## Impact

- Code: `privaci.schema.replicate`, `privaci.schema.objects`, `privaci.schema.ddl`,
  pipeline `run_lifecycle` / streaming completion hook, catalog skip audits for
  triggers, config models + `privaci init` scaffold.
- Docs: `docs/configuration.md` object replication section; ADR note or small
  ADR amending 0008 (indexes only — FKs unchanged); CHANGELOG.
- Tests: unit/integration covering secondary index timing, trigger create
  post-load, `replicate_triggers: false`, resume interrupted in post-data.
- Commercial: report collectors may need phase-aware schema_objects if they
  assume pre-stream completeness (follow-up pin only if needed).
