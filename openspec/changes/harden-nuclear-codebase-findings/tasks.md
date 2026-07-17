## 1. Schema replication correctness

- [x] 1.1 Fix CHECK constraint DDL emission for `pg_get_constraintdef` shape
- [x] 1.2 Add integration fixture with live PostgreSQL CHECK; update unit fixtures
- [x] 1.3 Skip FK DDL to excluded / non-created referents
- [x] 1.4 Implement `null_orphan_fks` nulling on batch/cell path for nullable orphans
- [x] 1.5 Force binary COPY ineligible (and `require_binary` preflight fail) when orphan nulling applies
- [x] 1.6 Integration tests: exclude parent + nullable FK; flag true/false; require_binary conflict
- [x] 1.7 Exclude `_privaci` from `drop_create` schema drops
- [x] 1.8 Document null_orphan + dry-run/plan callout in `docs/configuration.md`

## 2. Run identity, resume, and CLI remediations

- [x] 2.1 Pair UsageMeter `register_run` / `final_meter` on persisted `run_id`
- [x] 2.2 Unit test meter id pairing; document resume (no double-register)
- [x] 2.3 Fail resume (exit 2) in replicate mode when schema snapshot is absent
- [x] 2.4 On resume with snapshot present, re-run idempotent `replicate_schema` before stream
- [x] 2.5 Implement `privaci run --force-restart` (truncate/drop_create only; reject fail)
- [x] 2.6 Replace all remediations that cited missing `--force-restart`
- [x] 2.7 Document exit **2** causes/remediations for resume-without-snapshot and force-restart+fail in `docs/error-codes.md`
- [x] 2.8 Update state-schema / operator docs for resume gate + force-restart

## 3. Observability and operator contracts

- [x] 3.1 Sync `docs/observability.md` + canonical OpenSpec to hashed redaction
- [x] 3.2 Fix exit-5 remediation (License Manager; no metering endpoint)
- [x] 3.3 Remove stale “matviews later phase” wording from configuration docs
- [x] 3.4 Document full audit `EventType` set in `docs/state-schema.md`
- [x] 3.5 Set `commercial_layer_present` from `is_commercial_installed()`
- [x] 3.6 Ensure every `skipped_object` payload includes `reason`
- [x] 3.7 Default-redact free-text `message`/`detail`/`cause` unless allowlisted
- [x] 3.8 Document current `created_object` / `skipped_object` audit shapes in
  `docs/state-schema.md` (definition-only / `definition_only_object` deferred
  to sibling `add-schema-replication-modes`)
- [x] 3.9 ADR-0007 scrub: CLI contract-version help; deployment/OpenSpec gaps as needed
- [x] 3.10 Fix docs README stale init-privaci-engine archive link; hand CLI gaps
- [x] 3.11 Document source-DB trust boundary (function bodies / indexdefs) as residual

## 4. Streaming and masking mediums

- [x] 4.1 Per-table (or non-cycle) commit so sibling failures keep checkpoints
- [x] 4.2 Extend `assert_safe_identifiers` to views/functions/sequences/constraints
- [x] 4.3 Limit uniqueness suffixing to single-column UNIQUE only
- [x] 4.4 CHANGELOG entries for Fixed/Changed behaviours above

## 5. Structural deepening (behaviour-preserving)

- [x] 5.1 Canonical `table_strategy` + `excluded_table_ids` helper; delete clones
- [x] 5.2 Split catalog snapshot serialize vs `state` persist; break import cycles
- [x] 5.3 Move skip/disposition policy out of catalog into schema/replication policy
- [x] 5.4 Add `record_event` dual audit+emit helper; use in lifecycle/runner
- [x] 5.5 Introduce `run-lifecycle` `open_run` / `stream_run` / `close_run`
- [x] 5.6 Thin CLI/`runner` to call run-lifecycle; dedupe catalog introspect helpers
- [x] 5.7 Decompose `cli/app.py` registration if still over line limit after 5.5

## 6. Verification

- [x] 6.1a `./scripts/ci-local.sh` green (unit/lint/mypy/coverage)
- [x] 6.1b `./scripts/ci-local.sh --integration` (or public capability suite
  with Postgres) green before PR — operator session
- [x] 6.2 Capability matrix/registry `public-harden-nuclear-findings`: CHECK
  round-trip, exclude-FK+null_orphan, require_binary conflict, force-restart×fail
  (resume-without-snapshot covered by unit tests in 2.3, not this integration cell)
- [x] 6.3 Re-run `nuclear-openspec` after mid-implementation drift; amend
  residuals (definition_only scrub, verification honesty, crash-window residual)
- [x] 6.4 Note commercial pin bump remains separate (schema-mode Unreleased)
