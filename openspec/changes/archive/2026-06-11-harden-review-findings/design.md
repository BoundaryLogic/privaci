## Context

The engine passes `ruff` and `mypy --strict` cleanly, but a full review found
defects that span multiple modules. Three are release-blocking; the rest are
hardening and maintainability work that is cheapest to land as one coordinated
pass because several findings share a root cause (naive identifier quoting, raw
value previews). This design covers the cross-cutting decisions; per-finding
mechanics live in `tasks.md` and the requirement deltas live in `specs/`.

Relevant constraints (`.cursorrules`, ADRs): treat all source/target-database
data as untrusted; never concatenate SQL with untrusted input; never log raw PII
or secret values; security-critical modules (`mask/`, `config/`, secrets) stay at
100% coverage; functions ≤40 lines, files ≤400 lines.

## Goals / Non-Goals

**Goals:**
- Make `privaci resume` work after a normal SIGINT/SIGTERM interrupt.
- Eliminate identifier-injection risk in all dynamically built SQL via one helper.
- Ensure the production pack-signing trust anchor is never the fixture key.
- Close PII/secret leakage paths in logs, errors, and reprs.
- Fix resume/state correctness gaps (PK cursor types, snapshot drift, fail-loud).
- Harden secrets backends (timeouts, cleanup, log-then-raise, file constraints).
- Land remaining maintainability nits so the beta starts clean.

**Non-Goals:**
- No new masking features, providers, or connectors.
- No change to the on-disk `_privaci` schema shape beyond what fail-loud requires
  (no migration of existing columns).
- No commercial-layer work (lives in `privaci-commercial`).
- Not reworking the deterministic-faker algorithm — only adding a seed delimiter.

## Decisions

### D1. One mandatory identifier-quoting helper

Add `quote_pg_identifier(name: str) -> str` (likely `privaci/sqlnames.py` or
`catalog/identifiers.py`) that doubles embedded `"` (Postgres rule `"` → `""`) and
rejects identifiers containing NUL or other control characters. Every site that
embeds a schema/table/column/PK name in SQL uses it; `qual` becomes
`f"{quote_pg_identifier(schema)}.{quote_pg_identifier(table)}"`. The existing
`# noqa: S608` lines stay only where the *entire* dynamic portion is now produced
by the helper, with the `# SECURITY:` comment updated to state the invariant.

**Alternatives considered:**
- *asyncpg/psycopg identifier adapter:* asyncpg has no first-class identifier
  quoting; rolling a tiny audited helper is simpler than pulling one in.
- *Validate-and-reject only (allowlist `[A-Za-z0-9_]`):* would break legitimate
  quoted identifiers (mixed case, spaces) that exist in real customer schemas.
- *Server-side `quote_ident()` everywhere:* requires an extra round-trip per
  identifier; only viable in set-returning catalog queries (already used there).

### D2. Resume gate matches all resumable terminal states

`find_resumable_run` queries `status IN ('in_progress','interrupted','failed')`
(parameterized list), ordered newest-first. On resume, the run is reset to
`in_progress` (clear `ended_at`) inside the same transaction that loads
checkpoints. Distinct gate-failure causes (no run vs config/source/salt drift) are
reported by fetching the latest run for the identity and comparing fields, so the
operator learns *which* condition failed (matches `state-and-audit` spec intent).

**Alternatives considered:**
- *Only add `interrupted`:* still strands caught-exception runs finalized as
  `failed`, which are legitimately resumable per-batch. Include `failed`.
- *Leave status `in_progress` on interrupt:* loses the audit signal that the run
  was interrupted; finalize-then-rematch keeps the audit trail honest.

### D3. Production trust anchor is injected, fixture key is test-only

`TRUSTED_PACK_PUBLIC_KEY` is resolved at runtime from a configured source
(environment variable / build-stamped constant), with a clear failure if absent
in a production build. The fixture key moves entirely into `tests/fixtures/packs`
and is used only via test override. A CI/release check asserts the shipped key is
not the fixture key.

**Alternatives considered:**
- *Hardcode the real key now:* we don't have the production keypair in-repo and a
  public key in source is fine, but it must be the *real* one; gate it on release
  rather than committing a placeholder that could ship.

### D4. Redaction is safe-by-default with a minimal preview

Event redaction (`observability/redact.py`) switches from a name-allowlist to
redacting any value unless explicitly marked structural/safe, and the preview
shrinks so short PII cannot be reconstructed (e.g. emit a length + short salted
hash prefix, never raw leading characters). `mask/safe_log.py` aligns. DSN
passwords are stripped via `urlparse` rebuild in both `ParsedSecretUri.__repr__`
and resolver error text; the log-redaction filter registers secrets regardless of
length; `Config.global_salt` becomes a `SecretStr`.

**Alternatives considered:**
- *Keep the allowlist but expand it:* deny-by-omission keeps reappearing as new
  event fields are added; invert the default instead.
- *Drop previews entirely:* a bounded non-reversible hint aids debugging without
  leaking; keep that, just make it non-reconstructable.

### D5. Checkpoint cursor covers all single-column PK types

`parse_checkpoint_cursor` gains branches for `uuid`, date/time, and boolean (and
falls back to asyncpg's text representation only for genuinely opaque types).
Resume additionally hashes the live catalog snapshot and compares to the stored
`source_schema_snapshot`, failing with a structured `PreflightError` on drift.

### D6. Structural refactors (behavior-preserving)

These are code-quality fixes from the structural review. They keep behavior
identical (the existing test suite is the guard) and exist to stop duplication and
keep files under the `.cursorrules` 400-line cap.

- **One CLI run context.** `execute_run` and `execute_resume` share a ~25-line
  prologue (license gate, DSN resolution, salt + fingerprint logging, signal-handler
  install/restore, `asyncio.run` wrapper). Extract `prepare_cli_run(...) ->
  RunContext` and `run_with_signal_handlers(coro_factory)`; both commands become
  "prepare → guarded run → echo". This removes the correctness-drift risk of the
  license/salt path diverging between run and resume, and lets `_resume.py` stop
  importing the private `_resolve_db_url` from a sibling.
- **Typer option aliases.** Replace the verbatim `--source`/`--target`/`--config`
  option declarations (repeated 5-6×) with shared `Annotated` aliases. Single source
  of help text/envvar; drops `cli/app.py` well under the cap.
- **Disposition dispatcher in the pipeline.** Split `_stream_all` into a pure
  `_plan_table(table, config, checkpoints) -> TableAction` (SKIP_DONE /
  SKIP_STRATEGY / FINALIZE_EMPTY / STREAM) plus one `_log_skip` helper, collapsing
  the three duplicated skip blocks and the doubled checkpoint-DONE check. Lift the
  fresh-run setup (introspect → snapshot → replicate → audit) into
  `_initialize_fresh_run`. Decomposition (not reshuffling) brings the file under cap.
- **Canonical `qual`.** Add `TableInfo.sql_ref` (the quoted SQL form, built on
  `quote_pg_identifier` from D1) next to the existing `.identifier`, and use it
  everywhere `f'"{schema}"."{table}"'` is currently re-derived. This is the same move
  that closes the D1 injection class — duplication and the bug die together.
- **Shared test config builder.** Extract the "exclude all tables except these"
  helper (`keep_only(catalog, {...})`) duplicated across integration tests.

**Alternatives considered:** a dispatch dict for `column_masker`'s `isinstance`
chain was explicitly rejected — on a closed action union terminated by
`assert_never` the chain is the idiomatic, exhaustiveness-checked form; a dict would
reduce legibility and lose mypy coverage. Left as-is.

## Risks / Trade-offs

- **Resume gate now resumes `failed` runs that failed for a non-transient reason.**
  → The existing five-condition gate (config/source/salt/snapshot) plus the new
  snapshot-drift check guards correctness; a genuinely bad run still fails again
  loudly and the operator can `--force-restart`.
- **Identifier helper applied broadly could change emitted SQL text.** → Behavior
  is identical for normal identifiers; add a hostile-identifier test and snapshot a
  few emitted statements to prove parity.
- **Safe-by-default redaction could over-redact a useful debug field.** → Provide
  an explicit structural-fields set for known-safe keys (ids, counts, names of
  tables) so operational events stay readable.
- **Pack-key injection adds a release step.** → Document in the release runbook and
  add the CI assertion so a fixture-keyed build cannot ship.
- **Structural refactors could change behavior unintentionally.** → They are
  behavior-preserving by definition; land them behind the existing unit + integration
  suite (100% on security-critical modules) and review emitted SQL/CLI help for parity.
  Keep them as separate commits from the security fixes so a regression bisects cleanly.

## Open Questions

- Where should the production pack public key come from at build time — a stamped
  constant in release CI, or a file baked into the image? (Leaning: release-CI
  stamp + image label, mirroring §15.13 contract-version labeling.)
- Should `failed` runs require an explicit `--resume-failed` flag rather than being
  picked up automatically, to avoid silently resuming a logically broken run?
