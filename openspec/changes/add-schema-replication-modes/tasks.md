# Tasks: add-schema-replication-modes

> Phased delivery. Each phase is independently mergeable. Commercial report collectors
> (created_object / definition_only_object) ship in the commercial repo after Phase 2 —
> see design.md cross-repo follow-up.

## Phase 1 — assume_existing + idempotent table DDL

- [ ] 1.1 Add `schema_mode: replicate | assume_existing` to `Config` (default `replicate`)
- [ ] 1.2 Implement `assume_existing` preflight: validate in-scope tables exist with
      compatible column types; exit 3 on mismatch
- [ ] 1.3 Skip `replicate_schema` when `schema_mode: assume_existing`
- [ ] 1.4 Make unique index DDL idempotent (`IF NOT EXISTS` or duplicate guard)
- [ ] 1.5 Make foreign-key DDL idempotent (check `pg_constraint` before `ADD CONSTRAINT`)
- [ ] 1.6 Unit tests: assume_existing happy path, missing table, type mismatch
- [ ] 1.7 Integration test: load into prebuilt Demo Corp target with `on_existing_data: truncate`
- [ ] 1.8 Update `docs/configuration.md`, `CHANGELOG.md` [Unreleased]

## Phase 2 — functions + views (default-on) + audit taxonomy

- [ ] 2.1 Introspect functions/procedures + dependency graph (`postgres-catalog`)
- [ ] 2.2 Add `replicate_views` / `replicate_functions` config (default `true`)
- [ ] 2.3 Implement DDL replication: functions → views (topological order)
- [ ] 2.4 Skip `SECURITY DEFINER` views by default with `skipped_object` + reason
- [ ] 2.5 Add `EventType.CREATED_OBJECT`; emit for replicated views/functions
- [ ] 2.6 Update `iter_skipped_object_audits` — views no longer always skipped
- [ ] 2.7 Update Demo Corp e2e: views assert `created_object`, triggers `skipped_object`
- [ ] 2.8 Update `docs/observability.md`, `docs/test-fixtures.md`
- [ ] 2.9 **Commercial follow-up (separate PR):** `report_summary` collectors for
      `created_object` and updated `skipped_object` reasons

## Phase 3 — materialized views (definition-only)

- [ ] 3.1 Add `replicate_materialized_views` (default `false`) and
      `refresh_materialized_views` (default `false`)
- [ ] 3.2 Emit `CREATE MATERIALIZED VIEW … WITH NO DATA` from `pg_get_viewdef`
- [ ] 3.3 Add `EventType.DEFINITION_ONLY_OBJECT`; payload `contents_copied: false`
- [ ] 3.4 Optional post-load `REFRESH MATERIALIZED VIEW` in dependency order
- [ ] 3.5 Integration test: matview shell exists, no source bytes, refresh derives from
      masked tables
- [ ] 3.6 Demo Corp e2e: `tickets_open_mv` → `definition_only_object`
- [ ] 3.7 **Commercial follow-up:** PDF/Markdown section for definition-only objects

## Phase 4 — release

- [ ] 4.1 `./scripts/ci-local.sh` green on public repo
- [ ] 4.2 Bump engine tag; commercial `.engine-pin` + image release (maintainer)
- [ ] 4.3 Archive this change (`openspec archive add-schema-replication-modes`)
