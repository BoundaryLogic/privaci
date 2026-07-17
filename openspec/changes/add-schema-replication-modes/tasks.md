# Tasks: add-schema-replication-modes

> Phased delivery. Each phase is independently mergeable. Commercial report collectors
> (created_object / definition_only_object) ship in the commercial repo after Phase 2 —
> see design.md cross-repo follow-up.

## Phase 1 — assume_existing + idempotent table DDL + validation audit

- [x] 1.1 Add `schema_mode: replicate | assume_existing` to `Config` (default `replicate`)
- [x] 1.2 Add `passthrough_copy: auto | require_binary | batch` (default `auto`)
- [x] 1.3 Implement `assume_existing` preflight: validate in-scope tables exist with
      compatible column **name + type** (order-independent); exit **2** on mismatch
- [x] 1.4 Gate binary COPY on physical order/type equality; honour `passthrough_copy`
      (`auto` fall back to named batch; `require_binary` fail; `batch` never binary)
- [x] 1.5 Emit `schema.validated` audit row on successful assume_existing validation
- [x] 1.6 Emit `schema.validation_failed` audit row on refusal (before exit 2; respect
      `audit_log: false`; identifiers only, no PII values)
- [x] 1.7 Skip `replicate_schema` when `schema_mode: assume_existing`
- [x] 1.8 Make unique index DDL idempotent (`IF NOT EXISTS` or duplicate guard)
- [x] 1.9 Make foreign-key DDL idempotent (check `pg_constraint` before `ADD CONSTRAINT`)
- [x] 1.10 Unit tests: assume_existing happy path, missing table, type mismatch,
      `passthrough_copy` modes, validation audit events
- [x] 1.11 Integration test: load into prebuilt Demo Corp target with
      `on_existing_data: truncate`
- [x] 1.12 Update `docs/configuration.md`, `docs/observability.md`, `docs/error-codes.md`
      as needed, `CHANGELOG.md` [Unreleased]
- [x] 1.13 Collision policy: under `assume_existing` + `on_existing_data: fail`, refuse
      only when in-scope tables have rows (empty prebuilt tables allowed); document that
      identity/`SERIAL` absence does not permit populated loads without truncate; update
      operator docs + unit tests

## Phase 2 — functions + views + elevated dispositions + object audit taxonomy

- [ ] 2.1 Introspect functions/procedures + dependency graph + elevated markers
      (`postgres-catalog`)
- [ ] 2.2 Add `replicate_views` / `replicate_functions` config (default `true`)
- [ ] 2.3 Add `elevated_objects` map (`schema.object` → `replicate` | `skip`)
- [ ] 2.4 Implement DDL replication: functions → views (topological order); apply
      elevated dispositions (deny unresolved)
- [ ] 2.5 `privaci init` / `plan`: detect elevated objects; scaffold empty map; print
      ACTION REQUIRED listing objects needing disposition
- [ ] 2.6 Add `EventType.CREATED_OBJECT`; emit for replicated views/functions
- [ ] 2.7 Update `iter_skipped_object_audits` — views no longer always skipped; elevated
      `skip` disposition emits `skipped_object` with reason `elevated_object_skipped`
- [ ] 2.8 Update Demo Corp e2e: non-elevated views assert `created_object`, triggers
      `skipped_object`; cover at least one elevated disposition path
- [ ] 2.9 Update `docs/configuration.md`, `docs/observability.md`, `docs/cli-reference.md`
      (init), `docs/test-fixtures.md` — elevated policy prominent
- [ ] 2.10 **Commercial follow-up (separate PR):** `report_summary` collectors for
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
