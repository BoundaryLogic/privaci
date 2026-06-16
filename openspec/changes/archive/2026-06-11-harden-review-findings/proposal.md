## Why

A full code review of the engine (clean `ruff` + `mypy --strict` baseline) surfaced
three correctness/security defects that must not ship in the public beta, plus a
set of hardening and maintainability items. The two highest-impact issues defeat
or endanger headline behavior: `privaci resume` cannot find a normally-interrupted
run, and dynamic SQL quotes identifiers without escaping embedded double-quotes on
paths that run `DROP SCHEMA` / `TRUNCATE`. A third issue ships a test/dev
pack-signing key as the "trusted" production key.

## What Changes

- **BREAKING (behavioral): fix the resume gate.** `find_resumable_run` matches only
  `in_progress`, but interrupted runs are finalized as `interrupted` (and crashed
  runs as `failed`). Resume after SIGINT/SIGTERM — the documented path — now works.
- **Centralize Postgres identifier quoting.** Introduce a single
  `quote_pg_identifier` helper that doubles embedded `"` and rejects NUL/control
  characters, and route every dynamic-SQL identifier (table/column/schema/PK) in
  `stream/`, `preflight/`, `schema/`, `verify/`, and `catalog/graph` remediation
  strings through it. Source/target identifiers are untrusted per ADR/`.cursorrules`.
- **Replace the pack-signing trust anchor.** Stop shipping the fixture key as
  `TRUSTED_PACK_PUBLIC_KEY`; load the production key from a build-time source and
  keep test keys test-only.
- **Harden PII/secret redaction.** Reduce the raw-value preview that can leak short
  PII (SSNs/names), make event redaction safe-by-default rather than name-allowlist,
  add a redacting `__repr__` to `ParsedSecretUri`, fully strip DSN passwords from
  error text, remove the 8-char floor on log redaction, and wrap `global_salt`.
- **Harden resume/state correctness.** Cover all PK types in checkpoint-cursor
  parsing (uuid/timestamp/bool), validate source-schema-snapshot drift on resume,
  fail loud when `mark_table_done` updates zero rows, and make `table_id` delimiter-safe.
- **Harden secrets backends.** Add client timeouts, context-managed cleanup, and
  log-then-raise on failure for AWS SM / Azure KV / Vault; add an allowlist + symlink
  + size guard to the file backend; validate env-var names.
- **Config/autodetect robustness.** Guard `regex_mask` patterns against ReDoS and
  reduce autodetect substring false positives (`pan`/`tel`/`cell`).
- **Structural refactors (behavior-preserving).** Remove the duplicated CLI run/resume
  prologue (license gate, DSN/salt resolution, signal-handler lifecycle) into one
  shared context helper; collapse repeated Typer option declarations into `Annotated`
  aliases; split `pipeline/runner._stream_all` into a table-disposition dispatcher +
  one skip helper and lift the fresh-run setup into its own function; give the
  repeated `qual` identifier expression a single canonical home (`TableInfo.sql_ref`
  on the quoting helper); and extract the duplicated test config builder.
- **Maintainability/nits.** Split over-cap files/functions, remove dead code, add a
  delimiter to the faker seed, and remove unused module loggers.

## Capabilities

### New Capabilities
- `sql-identifier-safety`: A single, mandatory mechanism for embedding PostgreSQL
  identifiers in dynamically built SQL, safe against hostile identifiers from an
  untrusted source/target database.

### Modified Capabilities
- `state-and-audit`: Resume gate matches non-`in_progress` finalized runs;
  checkpoint-cursor parsing covers all single-column PK types; resume validates
  source-schema-snapshot drift; checkpoint completion fails loud on zero-row updates.
- `secrets-resolver`: Connection-string passwords are fully redacted in all logs,
  errors, and reprs; redaction does not skip short secrets; backends apply timeouts
  and log-then-raise; the file backend constrains path/symlink/size.
- `observability`: Event redaction is safe-by-default and does not emit a raw-value
  preview large enough to leak short PII.
- `config-yaml`: `regex_mask` patterns are guarded against catastrophic backtracking;
  auto-detect substring rules avoid common false positives.

## Impact

- **Code:** `src/privaci/{stream,preflight,schema,verify,catalog}` (identifier
  quoting), `state/resume.py` + `pipeline/runner.py` (resume gate), `packs/keys.py`
  (+ build/release), `observability/redact.py`, `mask/safe_log.py`,
  `secrets/{parser,resolver,types,backends/*}`, `config/actions.py`,
  `autodetect/patterns.py`, `mask/faker/hash.py`.
- **Structural (behavior-preserving):** `cli/app.py`, `cli/_run.py`, `cli/_resume.py`
  (shared run context + `Annotated` options), `pipeline/runner.py` (dispatcher split),
  `catalog/models.py` (`TableInfo.sql_ref`), and `tests/integration/` (shared config
  builder). These are refactors with no requirement-level behavior change, so they add
  no new capabilities; they are tracked as tasks and gated by the existing test suite
  plus the `.cursorrules` 400-line/40-line limits.
- **Tests:** new hostile-identifier test; a CLI-path resume-after-interrupt test
  (current §18.6 test bypasses the gate); backend timeout/cleanup tests; redaction
  leak tests. Security-critical modules must stay at 100% coverage.
- **Docs:** `CHANGELOG.md`; `docs/error-codes.md` if any exit-code semantics shift
  (resume messages); `docs/secrets.md` (file-backend constraints).
- **Release gate:** the pack-signing key swap is a prerequisite for `v0.1.0-beta.1`
  (init-privaci-engine §18.8).
- **No new runtime dependencies.**
