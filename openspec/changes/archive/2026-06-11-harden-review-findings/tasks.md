## 1. Must fix — resume gate (state-and-audit)

- [x] 1.1 Change `find_resumable_run` to match `status IN ('in_progress','interrupted','failed')` using a parameterized list (`src/privaci/state/resume.py`)
- [x] 1.2 On resume, reset the matched run to `in_progress` and clear `ended_at` in the same transaction that loads checkpoints
- [x] 1.3 In `require_resumable_run`, fetch the latest run for the identity and emit distinct causes for: no run, config drift, source drift, salt drift
- [x] 1.4 Add a CLI-path integration test that interrupts a run (→ `interrupted`), then runs `privaci resume` and asserts zero loss/duplication (the §18.6 test bypasses the gate)
- [x] 1.5 Add a test that a `failed` run is resumable via the gate
- [x] 1.6 Update `docs/error-codes.md` / resume docs if any message/exit semantics change

## 2. Must fix — SQL identifier safety (sql-identifier-safety)

- [x] 2.1 Add `quote_pg_identifier(name: str) -> str` that doubles embedded `"` and rejects NUL/control chars (new module, e.g. `src/privaci/catalog/identifiers.py`)
- [x] 2.2 Unit tests: normal identifier, embedded-quote identifier, control-char rejection
- [x] 2.3 Route `stream/table.py` (`qual` at :80, `_insert_records` :214, fetch queries :289-296) through the helper
- [x] 2.4 Route `preflight/target.py` `_drop_user_schemas` (:84) and `_truncate_in_scope_tables` (:96-100) through the helper
- [x] 2.5 Route `schema/strategies.py` TRUNCATE (:21) through the helper
- [x] 2.6 Route `verify/structural.py` (:20-118) and `verify/runner.py` (:110-116) through the helper
- [x] 2.7 Fix `catalog/graph.py` remediation strings (:139) to quote schema/table/constraint and stop discarding the schema
- [x] 2.8 Update each `# SECURITY:` comment to state the helper invariant; keep `# noqa: S608` only where the dynamic portion is fully helper-produced
- [x] 2.9 Add an integration test with a hostile identifier (name containing `"`) that streams/truncates safely
- [x] 2.10 Reject NUL/control-char identifiers at catalog introspection time with a clear error

## 3. Must fix — pack-signing trust anchor (packs)

- [x] 3.1 Stop using the fixture key as `TRUSTED_PACK_PUBLIC_KEY`; resolve the production key from a build/release source (`src/privaci/packs/keys.py`)
- [x] 3.2 Move the fixture keypair entirely into `tests/fixtures/packs` and use it only via test override
- [x] 3.3 Add a release/CI check that fails if the shipped trusted key equals the fixture key
- [x] 3.4 Note the key-provisioning step in the release runbook and link from init-privaci-engine §18.8
- [x] 3.5 Confirm signature is still verified before any write (regression test)

## 4. Should fix — PII & secret redaction

- [x] 4.1 Make `observability/redact.py` safe-by-default: redact value-bearing fields unless explicitly classified structural; define the structural allowlist
- [x] 4.2 Replace the leading-chars preview in `redact_value` and `mask/safe_log.py` with a non-reversible hint (length + salted hash prefix)
- [x] 4.3 Add `ParsedSecretUri.__repr__` that never exposes the raw DSN (`secrets/parser.py`)
- [x] 4.4 Fix `_redact_uri` to strip the password via `urlparse` rebuild, not retain `user:pass` (`secrets/resolver.py:170`)
- [x] 4.5 Remove the 8-char floor in the secret log-redaction filter (`secrets/types.py:36`)
- [x] 4.6 Wrap `Config.global_salt` in `SecretStr` (`config/models.py`)
- [x] 4.7 Tests: SSN/name preview cannot be reconstructed; repr/error never contain a password; short secret is scrubbed

## 5. Should fix — secrets backends

- [x] 5.1 Add bounded connect/read timeouts to AWS SM, Azure KV, and Vault clients
- [x] 5.2 Release client resources deterministically (context manager / `finally`)
- [x] 5.3 Log-then-raise on backend failure with non-sensitive context (secret id / vault path / region)
- [x] 5.4 File backend: enforce allowed roots, refuse symlink escape, enforce max size (`secrets/backends/file.py`)
- [x] 5.5 Validate env-var names against `^[A-Za-z_][A-Za-z0-9_]*$` (`secrets/backends/env.py`)
- [x] 5.6 Tests: timeout path, file-backend traversal rejection, env-name validation

## 6. Should fix — resume/state correctness

- [x] 6.1 Extend `parse_checkpoint_cursor` to handle `uuid`, date/time, and boolean PK types (`state/resume.py:110`)
- [x] 6.2 Validate live-catalog vs stored `source_schema_snapshot` on resume; fail with structured `PreflightError` on drift
- [x] 6.3 Make `mark_table_done` check rowcount and raise `StateError` on zero rows (`state/checkpoints.py`)
- [x] 6.4 Make `table_id`/`parse_table_id` delimiter-safe for dotted schema names (`catalog/models.py:9-19`)
- [x] 6.5 Decide and implement handling for `CheckpointStatus.FAILED` on resume (retry vs `--force-restart`)
- [x] 6.6 Tests for each: UUID/timestamp/bool resume, snapshot-drift failure, zero-row mark, dotted schema round-trip

## 7. Should fix — config / autodetect robustness

- [x] 7.1 Guard `regex_mask` against ReDoS (bounded match time or pattern/input rejection) (`config/actions.py`, masking apply path)
- [x] 7.2 Tighten flags validation for `regex_mask`
- [x] 7.3 Scope autodetect `pan`/`tel`/`cell` substring rules to remove `company_name`-style false positives (`autodetect/patterns.py`)
- [x] 7.4 Tests: pathological pattern is bounded; `company_name` is not flagged as PAN

## 8. Nits — cleanup

- [x] 8.1 Add a delimiter/length-prefix to `compute_seed` inputs to remove concatenation ambiguity (`mask/faker/hash.py`); confirm existing fakes are regenerated/documented as a deterministic-output change
- [x] 8.2 Remove dead code: `catalog/graph._layer_index` and unset `LoadPlan.non_deferrable_cycles`
- [x] 8.3 Remove or use unused module loggers in `state/checkpoints.py`, `state/resume.py`, `state/schema.py`
- [x] 8.4 Improve `detectors._table_name_tokens` plural strip (avoid `"ss"`→`"s"`)
- [x] 8.5 Narrow `state/audit.py` `event_type: EventType | str` to `EventType` (or validate against allowlist)

## 9. Maintainability — length limits

- [x] 9.1 Split `pipeline/runner.py` (448 lines) below the 400-line cap
- [x] 9.2 Split `cli/app.py` (400 lines) below the cap
- [x] 9.3 Split `catalog/introspect.py` (395/400) — e.g. extract skipped-object fetchers into `catalog/skipped.py`
- [x] 9.4 Decompose >40-line functions: `secrets/resolver.resolve_secret`, `secrets/parser.parse_secret_uri`, `catalog/graph.build_load_plan`, `catalog/introspect` transaction body, `catalog/partitions.attach_partition_metadata`

## 11. Structural refactors (behavior-preserving)

- [x] 11.1 Extract a shared CLI run context: `prepare_cli_run(config_path, source, target) -> RunContext` (load config, license gate, DSN + salt resolution, fingerprint log) used by both `execute_run` and `execute_resume` (`cli/_run.py`, `cli/_resume.py`)
- [x] 11.2 Extract `run_with_signal_handlers(coro_factory)` owning `clear_interrupt`/`install_handlers`/try-finally/`restore_handlers`; use it in both commands
- [x] 11.3 Stop importing the private `_resolve_db_url` across modules; move it into the shared CLI helper module
- [x] 11.4 Replace duplicated Typer `--source`/`--target`/`--config` options with shared `Annotated` aliases; confirm `cli/app.py` is under 400 lines
- [x] 11.5 Split `pipeline/runner._stream_all` into `_plan_table(...) -> TableAction` dispatcher + one `_log_skip` helper (collapse the 3 skip blocks and the doubled checkpoint-DONE check)
- [x] 11.6 Lift the fresh-run setup (introspect → snapshot → replicate → partition/skipped audit) into `_initialize_fresh_run(...)`; confirm `pipeline/runner.py` is under 400 lines
- [x] 11.7 Add `TableInfo.sql_ref` (quoted SQL form on `quote_pg_identifier`) and replace every re-derived `qual` f-string with it (folds into tasks §2)
- [x] 11.8 Extract a shared `keep_only(catalog, {...})` test helper into `tests/integration/`; use it in `test_beta_gate_e2e.py` and `test_loadtest_1gb.py`
- [x] 11.9 Confirm behavior parity: full test suite green and a quick diff of emitted SQL / `--help` output shows no change

## 12. Verification

- [x] 12.1 `ruff check src/ tests/` clean
- [x] 12.2 `mypy src/ --strict` clean
- [x] 12.3 `pytest --cov=src --cov-fail-under=85` green; 100% for `mask/`, `config/`, secrets
- [x] 12.4 `pip-audit` clean
- [x] 12.5 No source file exceeds 400 lines; no function exceeds 40 lines (`.cursorrules`)
- [x] 12.6 Add `CHANGELOG.md` entries (Fixed/Security/Changed) for all landed items
- [x] 12.7 `openspec validate harden-review-findings --strict`
