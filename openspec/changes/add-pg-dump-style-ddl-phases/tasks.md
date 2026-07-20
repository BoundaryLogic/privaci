## 1. Config and models

- [x] 1.1 Add `replicate_triggers: bool = True` to `Config` (ignored under
      `assume_existing`; document; do not hard-fail solely for the flag)
- [x] 1.2 Scaffold `replicate_triggers` in `privaci init` / plan output
- [x] 1.3 Update generated config docs if applicable

## 2. Catalog — triggers

- [x] 2.1 Add `TriggerInfo` (or equivalent) with `pg_get_triggerdef` + parent table
- [x] 2.2 Wire introspection; keep rules/publications as skip-only
- [x] 2.3 Elevated checks for trigger functions via existing `elevated_objects`

## 3. Pre-data split

- [x] 3.1 Narrow `replicate_schema` to pre-data: schemas, extensions, sequences,
      DEFAULT/CHECK-required functions, tables, partitions, PK/UNIQUE, FKs
- [x] 3.2 Stop creating remaining functions/views/matview shells and non-unique
      indexes in pre-data
- [x] 3.3 Tag pre-data audit events with `ddl_phase: pre-data`
- [x] 3.4 Unit-test DEFAULT/CHECK function hoist into pre-data

## 4. Post-data apply

- [x] 4.1 Add `apply_post_data_ddl` (non-unique indexes, remaining functions,
      views, matview shells, triggers, refresh)
- [x] 4.2 Invoke from `stream_and_finish` after stream, **before**
      `finish_run(SUCCEEDED)`; on failure mark FAILED / do not SUCCEEDED
- [x] 4.3 Trigger emit + dependency order; honor `replicate_triggers`
- [x] 4.4 Move non-unique indexes (`replicate_all_indexes`) into post-data
- [x] 4.5 Tag post-data audits with `ddl_phase: post-data`
- [x] 4.6 Keep per-table `setval` in the data/stream path (do not move to
      post-data)

## 5. Skip audits / plan UX

- [x] 5.1 Stop unconditional trigger skips when `replicate_triggers` is true
- [x] 5.2 Keep rules/publications as `skipped_object`
- [x] 5.3 `privaci plan` lists pre-data vs post-data object membership

## 6. Docs and CHANGELOG

- [x] 6.1 Rewrite `docs/configuration.md` as pre-data / data / post-data table
- [x] 6.2 Document trigger semantics (no fire during mask COPY; DEFAULT function
      hoist; `replicate_triggers: false` escape)
- [x] 6.3 Note ADR-0008 unchanged for FKs; optional short ADR for phases
- [x] 6.4 CHANGELOG `[Unreleased]` BREAKING timing + trigger default-on
- [x] 6.5 Confirm exit-code mapping for post-data DDL failure in
      `docs/error-codes.md` (exit **2** via `PreflightError`, same as pre-data DDL;
      docs no longer claim exit 2 is only "before any writes")

## 7. Tests

- [x] 7.1 Unit: phase membership / DEFAULT function hoist / emit order
- [x] 7.2 Integration: unique index before stream; non-unique only after when
      `replicate_all_indexes`
- [x] 7.3 Integration: view/function absent mid-stream, present after post-data
- [x] 7.4 Integration: trigger created post-data by default; skipped when
      `replicate_triggers: false`; does not fire during COPY load
- [x] 7.5 Resume: all tables `done`, post-data interrupted → resume completes
      post-data without re-stream; never SUCCEEDED without post-data

## 8. Capability registry / roadmap

- [x] 8.1 Confirm roadmap entry for this change
- [x] 8.2 Register/update capability tests (extend
      `tests/integration/test_views_identity.py` and/or new trigger phase file)
  in `scripts/capability_test/registry.py`
