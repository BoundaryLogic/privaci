## Why

Customers fall into two deployment patterns: greenfield targets where PrivaCI should own
schema completeness, and prebuilt targets where migrations (Flyway, Liquibase, DBA-owned
DDL) already exist and the engine should validate-and-load only. Today `replicate_schema`
always attempts table DDL (with brittle index/FK creation on prebuilt targets), skips all
views and functions with a single `skipped_object` audit, and offers no explicit
`assume_existing` mode — blocking the common "load masked data into my staging schema"
workflow.

## What Changes

- Add **`schema_mode`** config: `replicate` (default, current greenfield behaviour) and
  `assume_existing` (skip DDL creation; validate shape; truncate/load per
  `on_existing_data`).
- In **`replicate` mode**, tier non-table catalog objects by safety:
  - **Tier 1 (default-on):** functions/procedures, then plain views (dependency order).
  - **Tier 2 (opt-in, definition-only):** materialized views — `CREATE … WITH NO DATA`
    only; never copy stored bytes; optional post-load `REFRESH`.
  - **Tier 3 (skipped):** triggers, rules, publications — remain `skipped_object` with
    documented reasons.
- Make table-level DDL **idempotent** where replication applies: `CREATE UNIQUE INDEX IF
  NOT EXISTS`, FK creation guarded against duplicates.
- Expand audit taxonomy:
  - `created_object` — DDL replicated (views, functions, tables if audited).
  - `definition_only_object` — matview shell without source byte copy.
  - `skipped_object` — unchanged semantics for customer-owned / unsafe objects.
- In **`assume_existing` mode**, emit validation warnings/errors for schema mismatches;
  do not emit `created_object` for objects PrivaCI did not create.
- Docs: `configuration.md`, `observability.md`, Demo Corp e2e expectations.
- **Cross-repo follow-up (commercial, separate change/PRs):** `report_summary` collectors
  for `created_object` / `definition_only_object`; summary markdown/PDF sections. Tracked
  as tasks **2.9** and **3.7** in `tasks.md` — not implemented in this public change.

## Capabilities

### New Capabilities

- `schema-replication-modes`: `schema_mode`, tiered object replication, validation path for
  prebuilt targets, and expanded object audit events.

### Modified Capabilities

- `schema-replication`: replace "views/matviews never replicated" with tiered replication
  rules; add `assume_existing` mode; idempotent index/FK DDL.
- `config-yaml`: new `schema_mode` field and matview replication flags.
- `postgres-catalog`: introspect functions/procedures and function dependencies for
  replication ordering.
- `observability`: document `created_object` and `definition_only_object` audit events.
- `state-and-audit`: normative requirements for the three object disposition event types.

## Impact

- **Public repo:** `src/privaci/schema/`, `src/privaci/preflight/`, `src/privaci/catalog/`,
  `src/privaci/config/`, `src/privaci/pipeline/lifecycle.py`, Demo Corp integration tests.
- **Plugin package (follow-up release):** `report_summary.py`, summary markdown/PDF, tests;
  no replication logic.
- **Official container image:** new engine tag → plugin pin bump → new container version.
- **Breaking (audit only):** Demo Corp plain views move from `skipped_object` to
  `created_object` in `replicate` mode; matviews become `definition_only_object` when
  enabled. Triggers/rules/publications remain `skipped_object`.

## Non-goals

- Trigger replication (even post-load) in v1 of this change.
- Rule or publication replication.
- Cross-database dialect support (MySQL matview semantics deferred to
  `add-state-schema-abstraction`).
- Commercial signed-report UI in this change (documented follow-up only).
