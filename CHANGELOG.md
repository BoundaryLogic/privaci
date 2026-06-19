# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-06-19

### Changed

- `run_preflight(..., defer_strict=True)` skips strict auto-detect validation so
  review commands can emit artifacts first; `privaci dry-run --report` writes the
  markdown report, then exits `3` when `strict_autodetect: true` and columns are
  uncovered.

## [1.0.0] - 2026-06-18

### Changed

- First stable release. Promotes the `v0.1.0-beta.7` codebase to GA;
  `CONTRACT_VERSION` remains `1.0`.

## [0.1.0-beta.7] - 2026-06-17

### Security

- Cloud secret backend error logs no longer include secret identifiers
  (`aws-sm://`, `azure-kv://`, `vault://` paths redacted before logging).

### Changed

- CI workflow: explicit least-privilege `permissions: contents: read`.

## [0.1.0-beta.6] - 2026-06-17

### Added

- Capability test harness (`scripts/capability_test/`, `scripts/capability-test.sh`,
  `scripts/capability-test-suite.sh`): selectable engine and extension capabilities,
  resource guards, version-2 reports with **Masking confidence** (leak probes,
  value-free verify, subsetting slice metrics) and infrastructure vs audit scopes.
- Integration masking audit: leak probes, action-shape checks, value-free verify,
  auto-detect Postgres test, and `public-spacy-ner` capability (hard-requires
  `spacy` + `en_core_web_sm` for demo-corp L2 columns).
- `RunEnhancer` contract hook for licensed plugin extensions; `detect-drift` and
  `preview` CLI entry points.
- Test fixtures: `subsetting-demo`, `autodetect-demo`, `json-mask-demo` SQL and
  configs for integration capabilities.

### Fixed

- Binary COPY passthrough now honors streaming row filters (FK subsetting).
- Binary COPY is skipped when a table uses cell post-processing (e.g. JSONB
  path masking) so transforms are not bypassed.
- Integration DB reset restores bootstrap `public` schema after full schema
  wipes (fixes spike SQL after autodetect fixture loads).

### Changed

- Local dev quickstart documents `pip install -e ".[nlp]"` and
  `python -m spacy download en_core_web_sm` as required for integration and
  capability suites that audit demo-corp masking.

## [0.1.0-beta.5] - 2026-06-16

### Changed

- Pipeline invokes ``UsageMeter.register_run`` before recording a new run and
  ``final_meter`` on successful completion (plugin contract lifecycle hooks).

## [0.1.0-beta.4] - 2026-06-16

### Added

- GitHub Pages workflow publishes MkDocs to `https://boundarylogic.github.io/privaci/`.
- [Release infrastructure runbook](docs/runbooks/release-infrastructure.md) for
  secrets, environments, and PyPI Trusted Publishing after a fresh repo.
- Implicit commercial-contract guard (`scripts/check_implicit_contracts.py`) and
  canonical catalog snapshot fixture (`tests/fixtures/canonical_catalog_snapshot.json`)
  so the commercial layer can detect drift in `_privaci.runs` columns, exit codes
  5/6, and snapshot JSON shape before going public.

### Changed

- Release workflow authenticates to GHCR with `GHCR_TOKEN` (org blocks
  `GITHUB_TOKEN` package writes).

## [0.1.0-beta.3] - 2026-06-16

### Security

- Bumped `cryptography` `46.0.7` → `48.0.1` to pick up OpenSSL security fixes
  in the statically linked wheels (Dependabot #3).

## [0.1.0-beta.2] - 2026-06-11

### Added

- Property-based masking-invariant tests (`tests/mask/test_masking_invariants.py`):
  determinism per provider, SHA-256 hash shape, salt isolation, total-function
  robustness over arbitrary UTF-8, and the None/empty contract.
- Integration tests for end-to-end determinism + salt isolation, an adversarial
  dataset (deep FK chain, 4-byte UTF-8, large jsonb, max numeric, arrays, bytea,
  inet) with byte-for-byte round-trip, and resume rejection on source schema drift.
- Opt-in mutation testing via `cosmic-ray` (`cosmic-ray.toml`, dev dependency);
  see `docs/local-development.md` §3.4. Closed three real test gaps in
  `regex_safe` surfaced by it (benign quantified-group acceptance, inclusive
  input-cap boundary, and the cap value).
- Manual PyPI publish workflow using Trusted Publishing (`.github/workflows/publish-pypi.yml`).
- Direct unit tests for the `run`/`dry-run`/`verify`/`resume` CLI orchestration
  (`tests/cli/test_execute_run.py`, `tests/cli/test_execute_resume.py`) and for
  the new TODO-format hook (`tests/scripts/test_check_todo_format.py`).

### Changed

- Batch sizing (`_estimate_row_width`) now sums per-column `pg_stats` average
  widths instead of assuming a flat 64 bytes/column, so tables with wide
  `TEXT`/`JSONB`/`BYTEA` columns auto-tune the batch row count realistically and
  avoid out-of-memory before the 256 MiB cap engages.
- The masking engine precomputes the per-table unique-column set once at
  construction, making per-cell uniqueness checks O(1) in the row hot path.
- Coverage now measures `cli/_run.py` and `cli/_resume.py` (previously omitted).
- The `todo-requires-issue` pre-commit hook is reimplemented as
  `scripts/check_todo_format.py` for portability across GNU/BSD userlands, and
  `make fixtures-verify` now uses a private `mktemp -d` directory instead of a
  predictable `/tmp` path (avoids symlink attacks on shared hosts).

### Fixed

- `emit_create_sequence` no longer splits sequence names on `.` and re-quotes
  them — which corrupted schema/sequence names legitimately containing a dot and
  double-quoted `pg_get_serial_sequence` output. The regclass-ready identifier
  is now emitted verbatim, consistent with the `nextval`/`setval` call sites.
- `privaci report --output PATH` creates missing parent directories before
  writing instead of raising `FileNotFoundError`.

### Security

- Release workflow now scans the published container image with Trivy and fails
  on fixable CRITICAL/HIGH OS/library vulnerabilities.
- Resolved all open Dependabot alerts: bumped `cryptography` `44.0.2` → `46.0.7`
  (GHSA-r6ph-v2qm-q3c2, GHSA-m959-cc7f-wv43), `aquasecurity/trivy-action`
  `0.28.0` → `0.35.0` (GHSA-69fq-xp46-6x23), and the dev toolchain `black`
  `25.1.0` → `26.3.1` (GHSA-3936-cmfr-pm3m) and `pytest` `8.3.4` → `9.0.3` with
  `pytest-asyncio` `0.25.3` → `1.4.0` (GHSA-6w46-j5rx-g56g).

## [0.1.0-beta.1] - 2026-06-11

First public beta of the community engine.

### Added

- `privaci --contract-version` prints the commercial-tier ABI version (`1.0`).
- Release channel policy (beta vs stable) documented in `docs/deployment.md`; beta
  tags publish `:beta` and `:edge` image aliases; stable tags publish `:latest`.
- OCI image labels `org.opencontainers.image.version` and
  `io.boundarylogic.contract_version` on release builds.
- CI guards: `scripts/check_contract_version.py`, `scripts/check_git_emails.py`,
  integration test job (`pytest -m "integration and not slow"` against
  `compose.dev.yml`).
- `scripts/generate_pack_signing_key.py` and `docs/runbooks/git-history-privacy.md`.

### Fixed

- Pinned `spacy` to `3.8.7`; `3.8.4` was yanked from PyPI and broke the release
  image build.
- Resume-gate integration test patched a stale `privaci.stream.table`
  `_fetch_batch_with_retry` symbol that moved to
  `privaci.stream.fetch.fetch_batch_with_retry` during the stream decomposition;
  the new CI integration job surfaced it.

### Security

- Secret backend hardening (`harden-review-findings` §5): AWS Secrets Manager,
  Azure Key Vault, and HashiCorp Vault clients now use bounded connect/read
  timeouts and release SDK resources in `finally` blocks. Backend failures are
  logged with non-sensitive context (secret id, vault path, region) before
  raising. The `file://` backend enforces allowed roots (`PRIVACI_SECRET_FILE_ROOTS`,
  default `/run/secrets` and `/var/run/secrets`), rejects symlinks, and caps
  file size at 64 KiB. `env://` variable names are validated at parse time.
- PII and secret redaction (`harden-review-findings` §4): observability
  redaction is safe-by-default (structural-field allowlist only); value previews
  use a non-reversible length + salted-hash hint. `ParsedSecretUri.__repr__` and
  resolver error paths never expose DSN passwords; short secrets are registered
  for log scrubbing; `Config.global_salt` is a `SecretStr`.
- Config-pack signing now fails closed (`harden-review-findings` §3): the engine
  no longer ships an embedded Ed25519 trust anchor. The fixture key that was
  previously shipped as `TRUSTED_PACK_PUBLIC_KEY` let anyone holding the test
  private key forge packs the engine would trust. The production key is now
  injected at runtime via `PRIVACI_PACK_PUBLIC_KEY` (hex-encoded 32-byte public
  key); when unset or invalid, `install-pack` aborts before touching any file and
  exits `3`. Added `scripts/check_pack_key.py` (CI gate) which fails the build if
  any 32-byte key literal appears in `src/privaci/packs/keys.py`, the
  `docs/runbooks/pack-signing.md` runbook, and tests covering the fail-closed
  path. The fixture public key now lives only under `tests/` and is injected via
  the same environment variable.
- SQL identifier injection hardening (`harden-review-findings` §2): added
  `privaci.catalog.identifiers.quote_pg_identifier`, the single mandatory helper
  for embedding schema/table/column names in dynamically-built SQL. It doubles
  embedded double-quotes and rejects NUL/control characters. Routed every
  dynamic-SQL site (`stream/table.py`, `stream/copy_binary.py`,
  `schema/strategies.py`, `preflight/target.py`, `verify/structural.py`,
  `verify/runner.py`) and the `catalog/graph.py` remediation hint through it via
  the new `TableInfo.sql_ref` property, and added an introspection-time guard
  (`assert_safe_identifiers`) so a hostile catalog fails loud during pre-flight.

### Fixed

- Empty masked tables no longer fail at `mark_table_done` when the source table
  has zero rows: the masked streaming path now seeds an initial checkpoint before
  the batch loop (thermo review P1).
- `privaci resume` no longer flips an interrupted/failed run back to
  `in_progress` when schema-drift validation aborts (thermo review P2): the
  resume gate is split into a read-only `resolve_resumable_run` and a mutating
  `reopen_resumable_run`, and the run is re-opened only after the drift snapshot
  check passes.
- Generated config schema no longer advertises `global_salt` as a `{_value}`
  object (thermo review P2): the `SecretStr` field renders as a nullable string
  in `docs/generated/mask-rules.schema.json` and the configuration reference.

### Changed

- `regex_mask` substitution runs in-process with a compiled-pattern cache and no
  longer dispatches each cell to a worker thread (thermo review P2). CPython
  holds the GIL during a match, so the former per-cell wall-clock timeout could
  not preempt a runaway match while adding thread overhead; the parse-time shape
  screen (now also catching quantified alternation) plus the per-value input cap
  are the effective ReDoS guards.
- Function-length compliance (`harden-review-findings` §12.5): decomposed the
  remaining 28 functions that exceeded the 40-line `.cursorrules` cap; split
  `stream/table.py` into `stream/fetch.py`, `stream/batch_write.py`, and
  `stream/models.py`. Pipeline abort handling now uses an explicit
  `PipelineSession` plus typed `except` branches (no `run_id_box` /
  `sys.exc_info()`).
- Structural refactors (`harden-review-findings` §11): shared CLI
  `prepare_cli_run` / `run_with_signal_handlers` / public `resolve_db_url` in
  `cli/context.py`; `TableAction` disposition planning in `pipeline/table_plan.py`;
  integration tests share `tests/integration/catalog_config.keep_only`.
- Maintainability splits (`harden-review-findings` §9): `pipeline/runner.py` now
  delegates to `pipeline/lifecycle.py` and `pipeline/streaming.py`; CLI shared
  options live in `cli/options.py`; skipped-object introspection moved to
  `catalog/skipped.py`; long functions in secrets parsing/resolution, FK graph
  planning, introspection, and partition attachment were decomposed.
- Deterministic faker seeds (`harden-review-findings` §8.1): `compute_seed` now
  length-prefixes each input segment before hashing, removing concatenation
  ambiguity. Masked values for the same salt/column/input will differ from
  earlier engine builds — re-baseline any golden fixtures after upgrading.

### Fixed

- Config and auto-detect robustness (`harden-review-findings` §7): `regex_mask`
  rejects catastrophic-backtracking pattern shapes at parse time (an unbounded
  quantifier over a group that itself contains a nested quantifier or
  alternation) and caps per-value input length at run time; only known `re`
  compile flags are accepted. Auto-detect `pan`/`tel`/`cell` rules use
  delimiter-bounded matching so names like `company_name` are not misclassified
  as PAN/phone columns.
- Resume/state correctness (`harden-review-findings` §6): checkpoint cursors now
  coerce `uuid`, boolean, and date/time PK types via the shared stream coercion
  table; resume compares the live source catalog to the stored
  `source_schema_snapshot` and fails pre-flight on drift; `mark_table_done`
  raises when no checkpoint row is updated; `parse_table_id` uses the rightmost
  dot so dotted schema names round-trip; `failed` table checkpoints are retried
  automatically on resume.
- Resume gate could not find normally-interrupted or failed runs
  (`harden-review-findings` §1): `find_resumable_run` only matched
  `status = 'in_progress'`, but a clean SIGINT records `interrupted` and a crash
  records `failed`, so `privaci resume` rejected exactly the runs it should
  recover. The gate now matches `in_progress`, `interrupted`, and `failed` via a
  parameterized status list, atomically re-opens the matched run (resets status
  to `in_progress` and clears `ended_at`) in the same transaction that loads
  checkpoints, and reports distinct causes for no-run vs. config/source/salt
  drift. Documented under `docs/error-codes.md#exit-code-2-pre-flight-failure`.

### Added

- 1 GB end-to-end load test (§18.3): a server-side fixture
  (`tests/integration/loadtest_data.py`) generates a multi-gigabyte dataset
  with `INSERT ... SELECT FROM generate_series(...)` so the Python process
  never materialises rows, and `tests/integration/test_loadtest_1gb.py` streams
  it through the masking pipeline while asserting row parity, FK integrity, no
  PII leakage, and **bounded memory** (peak RSS growth stays a small fraction of
  the dataset). Size and memory ceiling are configurable via
  `PRIVACI_LOADTEST_BYTES` and `PRIVACI_LOADTEST_MEM_CEILING_MB`; the test is
  marked `slow` + `integration` (excluded from default runs). Validated locally
  at 1.15 GB / 900k rows in ~40 s with flat system memory.
- Public beta release-gate hardening (§18, partial): end-to-end integration
  tests for a multi-table/self-referential DEFERRABLE foreign-key cycle
  (§18.4), a Rails-style polymorphic ("soft") foreign key that emits a
  `polymorphic_fk_warning` while the run still succeeds (§18.5), and a
  crash-then-resume run that verifies exact row parity with zero duplication
  (§18.6). New edge-case fixtures under `tests/fixtures/sql/edge-cases/`
  (`deferrable-cycle.sql`, `polymorphic-fk.sql`, `resume-many-rows.sql`).
- PEP 561 `py.typed` marker for the `privaci` package (shipped via
  `setuptools.package-data`) so downstream packages building against
  `privaci.contracts` (e.g. the commercial layer) receive the engine's types.
- Release-channel and contract-discoverability tasks (§15.12–15.13): beta vs.
  stable channels, the Marketplace image built only from a stable tag, OCI
  `contract_version` labels, a `privaci --contract-version` flag, and a
  release-gate check tying `CONTRACT_VERSION` to the engine major.

### Fixed

- UNIQUE-column faker collisions at scale (§18.3): the deterministic uniqueness
  suffix was 6 hex characters (24 bits), which birthday-collides at only a few
  thousand rows — contradicting the deterministic-faker spec's "1M distinct
  masked emails, no collisions" requirement. Widened the suffix to 16 hex
  characters (64 bits), making collisions negligible at 1M+ rows. Strengthened
  `test_unique_email_batch_has_no_collisions` to 50k rows so a regression cannot
  pass, and corrected the now-internally-consistent spec wording.

### Changed

- Raised security-critical masking coverage to 100% (§18.2): added unit tests
  for `ner_mask`/`regex_mask` flag handling, the `MaskingEngine` failure
  re-raise path, and every `privaci.mask.ner` model-loading branch (cached,
  missing SpaCy, missing model, parse failure). Overall coverage is 86%; all
  CI gates (black, isort, ruff, mypy --strict, pytest ≥85%, pip-audit) pass
  (§18.1).
- Public/commercial documentation scrub (§18.7) per ADR-0007: relocated the
  commercial billing-dimension ADR (`docs/adr/0003`), the original product
  proposal (root `proposal.md`), and the AWS Marketplace process spike
  (`docs/spikes/2.4-aws-marketplace.md`) to the private `privaci-commercial`
  repository, leaving a tombstone for ADR-0003 and removing pricing/tier/
  competitor and GTM references from the public engine docs and the
  `init-privaci-engine` proposal/design/spec. The engine retains only a stable
  `source_db_hash` for run identity; billing semantics are commercial. Amended
  ADR-0007 with the `openspec/` placement policy and release-channel cadence.

### Added

- Documentation site and first-run experience (§17): MkDocs Material scaffold
  (`mkdocs.yml`, `make docs-serve` / `make docs-build`), [`docs/quickstart.md`](docs/quickstart.md)
  (zero-to-first-masked-row), [`docs/architecture/overview.md`](docs/architecture/overview.md),
  [`SECURITY.md`](SECURITY.md), per-module `README.md` files under `src/privaci/`,
  and `scripts/generate_docs.py` which emits auto-generated CLI and configuration
  references under `docs/generated/` from the live Typer app and pydantic JSON
  Schema. CI includes a `docs-build` job; `make docs-generate --check` fails when
  generated files are stale. Expanded [`docs/extending-privaci.md`](docs/extending-privaci.md)
  with plugin and fake-provider registration examples.
- Deployment artifacts (§15): production `Dockerfile` (`python:3.12-slim`,
  non-root UID 10001, bundled `en_core_web_sm`), evaluation `compose.yml` using
  the image with read-only root + `/tmp` tmpfs, synthetic `deploy/demo-seed/`
  dataset, Helm chart (`deploy/helm/privaci/`) with CronJob + Secret refs +
  ConfigMap + hardened `securityContext`, `scripts/lint-helm.sh` and
  `scripts/verify-image.sh`, release workflow for multi-arch publish/SBOM/cosign,
  and `docs/deployment.md`. The `Dockerfile` installs and purges build tooling in
  a single layer (final image ~480 MB, under the 600 MB budget), `compose.yml`
  bind mounts carry the `:z` SELinux label for Podman on Fedora/RHEL, and the
  evaluation config copies `organizations` verbatim to preserve its `NOT NULL`
  FK referents. `scripts/verify-image.sh` honours `CONTAINER_ENGINE` (docker or
  podman). Adds `scripts/eval-stack.sh` (and `make eval-up` / `make eval-down`)
  that auto-detects an available compose engine — `docker compose`,
  `podman compose`, `podman-compose`, or `docker-compose` — and falls back to
  Podman when the Docker daemon is unreachable. The eval stack is verified on
  Docker Compose, the Podman Compose plugin, and standalone `podman-compose`;
  a "Docker vs Podman" section in `docs/deployment.md` documents the matrix.
  Adds a "Windows" section to `docs/deployment.md` covering Docker Desktop
  (WSL2 backend), WSL2, and PowerShell usage, cross-linked from
  `docs/local-development.md`.
- Observability (§14): structured JSON-lines event protocol on stdout via a new
  `privaci.observability` module. Each lifecycle moment (`run.start`,
  `schema.cloned`, `table.start`/`table.progress`/`table.end`, `run.end`,
  pre-flight, FK warnings, skipped objects, new tables, binary fallback) is one
  JSON object per line with an ISO-8601 microsecond timestamp and no ANSI codes.
  `table.progress` is throttled to at most once per 2 seconds per table; all
  value-bearing fields are redacted to `***` + 8 chars so captured logs are
  PII-safe. Adds `--prometheus-port` (off by default; lazy `prometheus-client`
  import) serving `/metrics`, and validated `--log-level` / `PRIVACI_LOG_LEVEL`
  control. Documented in `docs/observability.md`.
- Schema replication and streaming gaps (§11/§12): per-table `empty` and
  `truncate` strategies finalize checkpoints without streaming rows (`truncate`
  clears the target table first); catalog introspection for triggers, rules,
  and publications with `skipped_object` audit events; COPY-binary passthrough
  for unmasked tables; bounded batch prefetch between fetch and write;
  `binary_fallback` audit events for text-mode INSERT fallback; source batch
  fetch retry with exponential backoff (3 attempts); integration tests for
  passthrough copy, empty strategy, deferred FK cycles, and resume.
- Views and identity columns (§26): catalog introspection for plain and
  materialized views; schema replication skips them with `skipped_object`
  audit events; identity vs legacy `SERIAL` detection via
  `pg_get_serial_sequence`; `GENERATED ALWAYS` / `BY DEFAULT` preserved in
  DDL; post-stream `setval` on identity-owned sequences; streaming uses
  `INSERT ... OVERRIDING SYSTEM VALUE` when copying explicit values into
  `GENERATED ALWAYS` identity columns.
- Implied (soft) foreign-key detection (§25): catalog introspection flags
  columns named `*_email` / `*_username` / `*_user_id` / `*_mrn` that match a
  single-column UNIQUE column elsewhere with no catalog FK, emitting an
  `implied_fk_warning` that names both columns and suggests a `seed_alias`.
  Target tables are disambiguated by the column-name prefix. Warnings surface
  during `privaci run` / `catalog inspect` and never block the run; silence
  reviewed references via the new top-level `implied_fk_ignore` config list.
- PostgreSQL native partitioning (§24): catalog introspection for partitioned
  parents and children, `PARTITION BY` / `PARTITION OF` schema replication,
  per-child streaming with parent-inherited mask config, FK load-order edges
  propagated from parents to children, pre-flight rejection of sub-partitioning
  and per-child config overrides, `new_table` audit events with
  `reason: new_partition` when a partition appears between runs, and integration
  tests for Demo Corp `raw_events` / `patient_visits` plus per-partition resume.
- Streaming tables without a single-column primary key (including partitioned
  children with composite keys) now paginate with `ORDER BY ctid` instead of
  stopping after the first batch.
- `tests/integration/`: composable assertion helpers (`assert_no_pii_present`,
  `all_fks_valid`, `audit_count`, `partition_count`, …) and a Demo Corp
  end-to-end integration test (`test_demo_corp_e2e.py`) that runs the masking
  pipeline against the mini-tier fixtures when Postgres is available
  (`pytest -m integration`).
- Tier-1 mini-schema builders (`tests/fixtures/builders.py`) and pytest
  fixtures for per-test programmatic schemas; edge-case SQL under
  `tests/fixtures/sql/edge-cases/`; `compose.yml` demo stack; `compose.dev.yml`
  now seeds Demo Corp on first volume creation; pre-commit `verify-fixtures`
  hook (`make fixtures-verify`).
- `tests/fixtures/demo_corp/`: deterministic MedicalHelpDesk Corp generator with
  full-schema DDL (all four schemas, range/list partitions, views, ltree),
  provider modules, narrative L2 NER bait, and `generate` CLI
  (`--tier mini|demo|stress`). Committed **mini** tier SQL at
  `tests/fixtures/sql/demo-corp/`; `make fixtures-generate` /
  `make fixtures-verify` keep it in sync.
- Reference mask configs at `tests/fixtures/configs/` (`demo-corp.yaml`,
  `minimal.yaml`, `strict.yaml`).

- `privaci.autodetect`: zero-config PII column scanner with a finding/confidence
  model (`high` / `medium` / `low`), built-in name patterns, freeform gating via
  column type + `pg_stats.avg_width`, table-context priors (ADR-0011), strict-mode
  validation, pipeline merge (YAML overrides auto-detect), audit-log
  `column.pii_detected` events, and `privaci dry-run --report <path>` markdown
  output. Auto-detect is type-aware: actions whose output cannot fit the column
  type are skipped (e.g. `hash` on a `uuid` column resolves to `fake`/`uuid`).
- `privaci.stream`: masked-value coercion to native types for binary COPY, so
  non-text masked columns (`date`, `timestamp`, `numeric`, `uuid`, `boolean`,
  `bytea`, …) encode correctly instead of failing the asyncpg codec.
- `privaci verify`: value-free post-run auditor that compares the target against
  the source and reports only counts/rates/verdicts (never raw values). Checks
  per-column change rate (catches masks that didn't apply), passthrough drift,
  row-count parity, uniqueness preservation, and foreign-key integrity. Exits
  `1` on any failure for CI gating; `--sample-size` controls row-level sampling.
- `privaci resume`: continue an interrupted run from `_privaci.table_checkpoints`
  when config, source, and salt fingerprints match (five-condition gate per
  `state-and-audit/spec.md`).
- `privaci generate-ci`: emit GitHub Actions, GitLab CI, or Kubernetes CronJob
  templates (`--platform github-actions|gitlab-ci|k8s-cronjob`).
- `privaci install-pack`: fetch and verify Ed25519-signed config packs, preview
  the merge, and apply with confirmation (`--yes` to skip prompt;
  `--local-pack-dir` for offline use).
- `privaci report`: render a JSON compliance report stub (commercial PDF deferred).
- SIGINT/SIGTERM handling during `run`/`resume`: finish the in-flight batch,
  mark the run `interrupted`, and exit `130` via `RunInterruptedError`.
- `LicenseError` (exit `5`) and `DriftError` (exit `6`, commercial) error types.
- `docs/cli-reference.md`: full command reference documenting every `privaci`
  subcommand, its options/env vars, and examples; linked from the docs index,
  the configuration reference, and the root README (which now leads with
  operator-facing docs, not just developer/internal pages).
- ADR-0007 "Documentation & repository placement": policy for which docs stay in
  the public engine repo vs. move to `privaci-commercial`, plus the two-trigger
  timing (private repo at §19, doc scrub at the §18 beta gate). Tasks §18.7 adds
  the pre-publication doc-scrub checklist.
- ADR-0007 "Git history": scrub personal emails from author/committer fields
  and commit message bodies (`Co-authored-by:` trailers); tasks §18.7.6–18.7.7
  cover the rewrite steps and the GitHub PR-ref caveat before public launch.

### Changed

- `privaci run`: per-table progress output is now explicit — `Streaming
  <schema.table> (~N rows)` / `Streamed <schema.table>: N row(s)` and
  `Skipping <schema.table> (strategy=...)` — instead of an anonymous
  `Table streamed`. Structured `extra` fields (`event`, `table`, `rows`) are
  retained for the forthcoming JSON-lines observability output.

### Fixed

- Schema replication: create required Postgres extensions (e.g. ``ltree`` for
  ``geo_locations``) on the target before table DDL, and include the underlying
  Postgres error in DDL failure messages.
- Streaming: text-mode ``INSERT`` fallback for column types that asyncpg cannot
  encode on the binary COPY path (e.g. ``ltree`` on ``geo_locations``).
- UNIQUE-aware ``fake``/``dob`` on ``date`` columns: remap to a shifted ISO date
  instead of appending a ``__`` text suffix that breaks target type coercion.
- `privaci run`: streaming a masked non-text column (e.g. a faked `date` of
  birth) no longer crashes with `AttributeError: 'str' object has no attribute
  'toordinal'`; masked values are coerced to the destination column type and
  type-incompatible auto-detect actions are skipped with an audit reason.
- `privaci run` and `privaci dry-run`: wire the masking pipeline to the CLI
  with pre-flight checks (source/target connectivity, config table validation,
  `exclude` FK rules, `on_existing_data` policies), salt resolution from
  `global_salt` / `ANONYMIZATION_SALT`, `--dry-run`, and `--no-audit-table`.
- `privaci.mask`: per-table `MaskingEngine` with L1 actions (`fake`, `hash`,
  `regex_mask`, `passthrough`, `null`, `static`), optional L2 `ner_mask` via
  SpaCy, PII-safe DEBUG previews, and `L3NotInstalledError` for `ai_refine`.
- `privaci.schema`: catalog-driven DDL replication (`replicate_schema`) with
  unique-index and FK deferrability preservation, `replicate_all_indexes`
  opt-in, and pre-flight validation for `exclude` + dangling NOT NULL FKs.
- `privaci.stream`: keyset-batched table streaming with per-batch checkpoints,
  256 MiB batch-size cap heuristic, and deferred-constraint layer transactions.
- `privaci.pipeline`: programmatic `run_masking_pipeline()` entry point
  (introspect → replicate → stream → finish run) for integration tests ahead
  of `privaci run` (§13).
- `privaci.mask.faker`: salt-hashed deterministic fake generation with 19
  built-in providers, UNIQUE-aware suffix strategies, `seed_alias` FK
  consistency, `register_provider` extension API, and config validation for
  unknown provider names (exit 3). Property-based tests (`hypothesis`) cover
  determinism and collision resistance; 100% coverage on the faker package.
- `privaci.state`: the `_privaci` run-state and audit schema. Idempotent,
  single-transaction DDL for `runs`, `table_checkpoints`, `audit_log`, and a
  `schema_metadata` version marker; engine-version compatibility gate (exit 2
  on a future-version schema); run lifecycle (`start_run`/`finish_run` with
  UUIDv7 ids); batch-atomic checkpoint helpers (`write_checkpoint`/
  `mark_table_done`); an `AuditWriter` honoring the `audit_log: false` /
  `--no-audit-table` opt-out; and non-reversible identity fingerprints
  (`salt_fingerprint`, `source_db_hash`, `config_hash`).
- `docs/state-schema.md`: operator reference for the `_privaci` schema.
- Demo Corp (lite) sample data: `tests/fixtures/sql/demo-corp/` (schema + small
  deterministic seed) and `scripts/load_sample_data.py` to load it into the
  source database. Gives `privaci catalog inspect` a realistic multi-schema
  target (FK cycle, self-reference, cross-schema FKs, polymorphic FK, no-PK
  table) and seeds the foundation for the full Tier-2 generator.
- `privaci.catalog`: read-only PostgreSQL introspection (`pg_catalog` queries),
  typed `TableInfo`/`ColumnInfo` models, FK dependency graph with Kahn topo
  sort, cycle-deferral heuristic, polymorphic-FK warnings, self-cycle
  detection, and canonical JSON snapshot serialization/persistence helper.
- `privaci.config`: strict pydantic models for `mask-rules.yaml` (top-level
  options, per-table strategy, discriminated-union column actions), a YAML
  loader with path-attributed validation errors (exit 3), version-compatibility
  checks, and the `null`-on-`NOT NULL` pre-flight helper.
- CLI: `privaci validate` now validates the config, `privaci schema config`
  exports the config JSON Schema, and `privaci migrate-config` is scaffolded
  (no-op when `--from` equals `--to`).
- `docs/configuration.md`: operator reference for `mask-rules.yaml`.
- `docs/architecture/memory-model.md`: customer-facing memory model (bounded
  batches, backpressure, sizing guidance); ADR-0010 constant-memory streaming
  bounds.
- `docs/error-codes.md`: authoritative exit-code catalogue (0–6, 130) and the
  Context + Cause + Remediation error message format.
- `docs/README.md` documentation index; `.cursor/rules/documentation.mdc`
  documentation standards rule (docs updated with code, customer-first,
  AI-parseable, error-complete).
- Week-1 spikes: `compose.dev.yml`, `privaci.spikes` modules, `docs/spikes/`,
  `scripts/spikes/run_week1_spikes.py`, integration tests under `tests/spikes/`.
- `privaci.secrets` URI resolver: `env://`, `file://`, `aws-sm://`, `azure-kv://`,
  `vault://`, literal postgres URLs; optional vs required resolution; salt length check.
- Initial project scaffolding: Python 3.12 package, CLI entrypoint, ELv2 license.
- `privaci.contracts` plugin ABCs and community-mode fallbacks.
- `PrivaCIError` hierarchy and `SecretStr` redaction type.

### Fixed

- `privaci catalog inspect`: unanalyzed tables now show `~unknown rows` instead
  of leaking the internal `-1` statistics sentinel as `~-1 rows`.
- `privaci.catalog`: `build_load_plan` no longer loops indefinitely when a
  table with no foreign keys coexists with a pure FK cycle (e.g. a standalone
  table alongside a two-table cycle). The topological sort now tracks assigned
  tables explicitly, never re-emits a layer, and a bounded iteration guard
  converts any future regression into a `CatalogError` instead of a hang.

### Changed

- `proposal.md`: replaced stale "cursor-based pagination" wording with
  COPY-binary bounded-batch streaming (links to memory-model doc).
- Renamed the product from VaultPipe to **PrivaCI** (vendor: BoundaryLogic,
  boundarylogic.io). Python package `vaultpipe` → `privaci`, CLI command
  `vaultpipe` → `privaci`, internal state schema `_vaultpipe` → `_privaci`,
  env-var prefix `VAULTPIPE_*` → `PRIVACI_*`, and exception base
  `VaultPipeError` → `PrivaCIError`.
- `PrivaCIError` now renders a Context + Cause + Remediation message and
  carries a stable `exit_code` and `doc_anchor` per error class.
- CLI runs through a centralized error boundary (`privaci.cli._errors.run_cli`)
  that renders `PrivaCIError` and maps every outcome to a stable exit code.
- Pinned `click>=8.1.7,<8.5` to prevent the Typer/Click incompatibility that
  broke `--help` (`Parameter.make_metavar()` signature change).
- Developer docs: `docs/local-development.md`, `docs/test-fixtures.md`, ADRs.
