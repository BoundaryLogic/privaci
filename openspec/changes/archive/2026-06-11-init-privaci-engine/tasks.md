## 1. Project Scaffolding & Tooling

- [x] 1.1 Initialize `src/privaci/` package layout, `tests/` mirror, `pyproject.toml`
- [x] 1.2 Configure `pip-tools`, produce initial `requirements.in` and locked `requirements.txt` / `requirements-dev.txt`
- [x] 1.3 Configure `black`, `isort`, `ruff` (`E,F,W,I,N,UP,S,B,A`), `mypy --strict`, `pip-audit`
- [x] 1.4 Set up `pre-commit` hooks per `.cursorrules` (black, isort, ruff, pip-audit, custom TODO-without-issue hook)
- [x] 1.5 Author root `README.md` (quickstart, prerequisites, link to docs)
- [x] 1.6 Author `CHANGELOG.md` (Keep a Changelog format) and `LICENSE` (ELv2)
- [x] 1.7 Add `.env.example` with all required env vars and inline comments
- [x] 1.8 Add `.gitignore` (Python, `.env`, `*.pem`, `*.key`, `*.p12`, `dist/`, `.venv/`)
- [x] 1.9 Set up GitHub Actions CI: black/isort/ruff/mypy/pytest/pip-audit gates per `.cursorrules` §7
- [x] 1.10 Add ADR template stub and `docs/adr/` directory
- [x] 1.11 Author `docs/adr/0001-elv2-license.md` capturing license decision
- [x] 1.12 Author `docs/adr/0002-python-3-12-runtime.md` capturing runtime decision
- [x] 1.13 Author the billing-dimension ADR (commercial; relocated to `privaci-commercial` per §18.7.2 — public repo keeps a tombstone)
- [x] 1.14 Author `docs/adr/0004-state-in-target-database.md` (`_privaci` schema rationale)
- [x] 1.15 Author `docs/adr/0005-salt-ux-no-silent-default.md`
- [x] 1.16 Author `docs/adr/0006-copy-binary-streaming.md`
- [x] 1.17 Author `docs/adr/0007-public-commercial-split.md`
- [x] 1.18 Author `docs/adr/0008-fk-strategy-topo-sort-deferred.md`
- [x] 1.19 Author `docs/adr/0009-postgres-native-partitioning.md`
- [x] 1.20 Author `docs/local-development.md` (already drafted) and `docs/test-fixtures.md` (already drafted)

## 2. Architecture Spike (must complete before locking architecture)

- [x] 2.1 Spike: COPY-binary pipe round-trip in Python with `asyncpg` against local Postgres
- [x] 2.2 Spike: measure SpaCy `en_core_web_sm` throughput on representative freeform-text fixtures (target: ≥1k rows/sec)
- [x] 2.3 Spike: cyclic-FK load with `SET CONSTRAINTS ALL DEFERRED` end-to-end
- [x] 2.4 Spike: confirm AWS Marketplace listing terms work for one-shot batch jobs (commercial follow-up tracked in `privaci-commercial`; not code)
- [x] 2.5 Document spike findings in `docs/spikes/` and update `design.md` Open Questions if any walls are found

## 3. Shared Foundations (`privaci.errors`, `privaci.contracts`)

- [x] 3.1 Implement `PrivaCIError` base + per-module subclasses (`ConfigError`, `CatalogError`, `MaskingError`, `StateError`, `SecretError`, `L3NotInstalledError`)
- [x] 3.2 Implement `SecretStr` type with redacting `__repr__`/`__str__` and a logging filter
- [x] 3.3 Define `privaci.contracts` ABCs: `LicenseValidator`, `UsageMeter`, `LLMConnector`, `ReportRenderer`, `Notifier`, `DriftDetector` (per `commercial-tier-contract` spec)
- [x] 3.4 Implement community-mode no-op fallbacks for each contract
- [x] 3.5 Add `CONTRACT_VERSION` constant
- [x] 3.6 Add entry-point discovery via `importlib.metadata` for `privaci.plugins` group
- [x] 3.7 Unit tests for each fallback (100% coverage — counts as security-critical)
- [x] 3.8 Author `docs/extending-privaci.md` explaining the plugin model

## 4. Secrets Resolver (`privaci.secrets`)

- [x] 4.1 Implement URI parser for `aws-sm://`, `azure-kv://`, `vault://`, `env://`, `file://`, literal `postgres://`
- [x] 4.2 Implement `aws-sm` resolver via `boto3` (lazy import; only loaded if scheme is used)
- [x] 4.3 Implement `azure-kv` resolver via `azure-identity` + `azure-keyvault-secrets`
- [x] 4.4 Implement `vault` resolver via `hvac`
- [x] 4.5 Implement `env` and `file` resolvers
- [x] 4.6 Wire the centralized log-redaction filter to scrub resolved secrets
- [x] 4.7 Implement salt length validation (≥32 chars) post-resolution
- [x] 4.8 Required vs optional secret classification mechanism
- [x] 4.9 Unit tests for every scheme (positive + negative); integration tests use moto / azurite where available; 100% coverage (security-critical)

## 5. Config Layer (`privaci.config`)

- [x] 5.1 Define top-level pydantic model: `version`, `global_salt`, `on_existing_data`, `strict_autodetect`, `batch_size`, `audit_log`, `auto_detect`, `tables`
- [x] 5.2 Define `TableConfig` with `strategy` enum + `columns` mapping
- [x] 5.3 Define discriminated-union action models: `FakeAction`, `RegexMaskAction`, `HashAction`, `PassthroughAction`, `NullAction`, `StaticAction`, `NerMaskAction`, `AiRefineAction`
- [x] 5.4 Set `model_config = ConfigDict(extra='forbid')` on every model
- [x] 5.5 Implement YAML loader with line/col error attribution
- [x] 5.6 Implement `privaci schema config` to export JSON Schema
- [x] 5.7 Implement `privaci validate` subcommand (config validation; DB connectivity check wired in §13 pre-flight)
- [x] 5.8 Implement `privaci migrate-config` subcommand (no-op for v1.0 → v1.0, scaffolded for future migrations)
- [x] 5.9 Wire validation error → exit code `3` with actionable messages
- [x] 5.10 Reject `action: ai_refine` when commercial layer absent (config-level)
- [x] 5.11 Reject `on_existing_data: append` in MVP
- [x] 5.12 Reject `action: null` on `NOT NULL` columns (`check_null_actions` helper; catalog wiring in §6/§13)
- [x] 5.13 Unit tests covering every validation rule (positive + negative parametrized); 100% coverage (security-critical)

## 6. Postgres Catalog (`privaci.catalog`)

- [x] 6.1 Implement `pg_class` / `pg_attribute` / `pg_constraint` / `pg_namespace` introspection queries (parameterized — never string-concat)
- [x] 6.2 Build `TableInfo` and `ColumnInfo` dataclasses (`__slots__`, `__repr__`)
- [x] 6.3 Implement FK graph builder using `networkx` or a hand-rolled DAG
- [x] 6.4 Implement Kahn-style topological sort producing layer lists
- [x] 6.5 Implement cycle detection + lowest-cost-edge selection heuristic
- [x] 6.6 Implement polymorphic-FK pattern detector (warning only)
- [x] 6.7 Implement self-referential FK detector
- [x] 6.8 Skip `pg_*`, `information_schema` system schemas
- [x] 6.9 Persist canonical-JSON `source_schema_snapshot` to `_privaci.runs` (`persist_source_schema_snapshot`; requires §7 DDL)
- [x] 6.10 Integration tests using compose Postgres fixtures (`@pytest.mark.integration`) covering acyclic, self-ref, cycle, and polymorphic scenarios

## 7. State & Audit Schema (`privaci.state`)

- [x] 7.1 Define SQL DDL for `_privaci.runs`, `_privaci.table_checkpoints`, `_privaci.audit_log` (+ `schema_metadata` version marker)
- [x] 7.2 Implement idempotent schema creation (`CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, single transaction)
- [x] 7.3 Implement engine-version compatibility check (refuse to run against future-version state; exit 2)
- [x] 7.4 Implement run-start insert + run-end update flow (`start_run`/`finish_run`, UUIDv7 ids)
- [x] 7.5 Implement checkpoint-write helper that participates in the streaming transaction (`write_checkpoint`/`mark_table_done`)
- [x] 7.6 Implement audit-log writer with `event_type` enum + `payload` jsonb (`AuditWriter`)
- [x] 7.7 Implement `salt_fingerprint = sha256(salt)[:16]` computation
- [x] 7.8 Implement `source_db_hash = sha256(host:port/dbname)` computation
- [x] 7.9 Implement `--no-audit-table` flag honoring (state layer: `AuditWriter(enabled=...)`; CLI flag wired with `run` command)
- [x] 7.10 Integration tests for schema creation, idempotency, checkpoint atomicity, run-state transitions

## 8. Deterministic Faker (`privaci.mask.faker`)

- [x] 8.1 Implement core hash → index function (`compute_seed`, `normalize_input`, `seed_to_index`)
- [x] 8.2 Build static fake libraries for: first_name, last_name, full_name, email-local, fake-domains, phone, address, street, city, postcode, country, dob, ip_address, ssn, credit_card, username, company, job_title
- [x] 8.3 Implement `FakeProvider` ABC + registry (`register_provider`, `known_providers`)
- [x] 8.4 Implement built-in providers per `deterministic-faker/spec.md` action catalog
- [x] 8.5 Implement UNIQUE-aware suffix logic (text suffix, email-local +tag, numeric remap, UUID/password passthrough)
- [x] 8.6 Implement `seed_alias` resolution for FK columns (`FakeRequest.hash_path`)
- [x] 8.7 Implement Luhn-valid test-BIN credit-card generator
- [x] 8.8 Implement SSA-reserved-range SSN generator (`000-099-XXXX`)
- [x] 8.9 Wire `register_provider(name, cls)` extension API (+ config validation for unknown providers)
- [x] 8.10 Property-based tests with `hypothesis`: determinism, FK consistency, UNIQUE-aware uniqueness; 100% coverage (security-critical)

## 9. Auto-Detect (`privaci.autodetect`)

- [x] 9.1 Define pattern library (Python data; YAML pack extension deferred to `install-pack`)
- [x] 9.2 Implement column-name pattern matcher (substring + regex)
- [x] 9.3 Implement freeform-text heuristic (avg length ≥ 200, type `text`/`varchar(>=500)`, table context)
- [x] 9.4 Wire detection into the masking pipeline as a fall-through default
- [x] 9.5 Implement `strict_autodetect` config → exit `3` with column list (CLI flag deferred)
- [x] 9.6 Write detection results to `_privaci.audit_log`
- [x] 9.7 Implement `privaci dry-run --report <path>` markdown writer
- [x] 9.8 Unit tests for built-in patterns + confidence scoring

## 10. Masking Pipeline (`privaci.mask`)

- [x] 10.1 Implement `MaskingEngine` (per-table, stateless after construction)
- [x] 10.2 Wire L1 actions: `fake`, `regex_mask`, `hash`, `passthrough`, `null`, `static`
- [x] 10.3 Implement NULL-passthrough + empty-string handling
- [x] 10.4 Integrate SpaCy `en_core_web_sm` for L2 `ner_mask`
- [x] 10.5 Implement entity → deterministic-faker replacement
- [x] 10.6 Implement PII-safe logging (truncate to 8 chars at DEBUG, redact above)
- [x] 10.7 Wire `L3NotInstalledError` raising for `ai_refine` actions in community mode
- [x] 10.8 Implement column-level passthrough override priority
- [x] 10.9 Unit + property tests for purity, determinism, NULL preservation; 100% coverage (security-critical)

## 11. Schema Replication (`privaci.schema`)

- [x] 11.1 Implement DDL emitter for tables, columns, PKs
- [x] 11.2 Implement unique-index replication
- [x] 11.3 Implement FK replication with original `DEFERRABLE` flags preserved
- [x] 11.4 Implement check-constraint replication
- [x] 11.5 Implement sequence creation + post-load `setval`
- [x] 11.6 Honor per-table strategy: `transform`, `exclude`, `empty`, `truncate` (MVP: `transform` + `exclude` DDL skip; row streaming for `transform` only)
- [x] 11.7 Implement `replicate_all_indexes: true` opt-in path
- [x] 11.8 Implement pre-flight `exclude`-with-dangling-FK check
- [x] 11.9 Skip triggers / rules / matviews / publications with audit-log entries
- [x] 11.10 Integration tests against fixture schemas (unit tests + pipeline integration; full DDL fixture suite deferred)

## 12. Streaming Pipeline (`privaci.stream`)

- [x] 12.1 Implement asyncpg COPY-binary source-side decoder (MVP uses `fetch` + `copy_records_to_table`)
- [x] 12.2 Implement asyncpg COPY-binary target-side encoder (MVP uses `fetch` + `copy_records_to_table`)
- [x] 12.3 Wire in-process row mutation between the two COPY pipes
- [x] 12.4 Implement backpressure via bounded async queue
- [x] 12.5 Implement per-batch checkpoint commit (single transaction)
- [x] 12.6 Implement auto-tune batch size based on row width (≤256 MB cap)
- [x] 12.7 Implement binary type codec for required types (masked-value coercion in `stream/coerce.py`; full custom codec deferred)
- [x] 12.8 Implement text-mode fallback for unsupported types (with audit entry)
- [x] 12.9 Implement cycle-load transaction with `SET CONSTRAINTS ALL DEFERRED`
- [x] 12.10 Implement source-connection retry (3 attempts, exponential backoff)
- [x] 12.11 Implement composite/non-monotonic PK fallback to table-level checkpoint
- [x] 12.12 Integration tests: passthrough copy, masking copy, mid-run kill + resume, FK cycle (partial: `tests/pipeline/test_runner_integration.py`)

## 13. Pre-flight & CLI (`privaci.cli`, `privaci.preflight`)

- [x] 13.1 Wire `typer` app with all subcommands: `run`, `dry-run`, `validate`, `verify`, `gen-salt`, `generate-ci`, `install-pack`, `migrate-config`, `resume`, `report`
- [x] 13.2 Implement default-subcommand-is-`run` behavior
- [x] 13.3 Implement signal handlers (SIGINT/SIGTERM → graceful checkpoint flush + exit `130`)
- [x] 13.4 Implement `gen-salt` using `secrets.token_hex(32)` (64 chars)
- [x] 13.5 Implement `generate-ci --platform github-actions`
- [x] 13.6 Implement `generate-ci --platform gitlab-ci`
- [x] 13.7 Implement `generate-ci --platform k8s-cronjob`
- [x] 13.8 Implement `install-pack` with manifest signature verification (Ed25519)
- [x] 13.9 Implement merge-preview prompt for `install-pack`
- [x] 13.10 Wire all 10 pre-flight checks per `engine-cli/spec.md` (MVP: checks 1–9; commercial entitlement #10 via license validator stub)
- [x] 13.11 Wire exit codes 0/1/2/3/4/5/6/130 (6 via `DriftError` stub; commercial drift detection lives in `privaci-commercial`)
- [x] 13.12 Implement `resume` subcommand with the five-condition gate
- [x] 13.13 Unit + CLI integration tests using `typer.testing.CliRunner` (unit tests; full Demo Corp `privaci run` e2e deferred to §23)

## 14. Observability (`privaci.observability`)

- [x] 14.1 Implement JSON-lines logger (stdout, structured, ISO-8601 microseconds)
- [x] 14.2 Define and emit all 14 event types from `observability/spec.md`
- [x] 14.3 Implement `table.progress` 2-second throttle
- [x] 14.4 Implement PII redaction at the event-render layer
- [x] 14.5 Implement optional Prometheus `/metrics` endpoint (off by default)
- [x] 14.6 Implement `--log-level` flag + `PRIVACI_LOG_LEVEL` env var
- [x] 14.7 Integration test: capture stdout, validate every line parses (`json.loads` per line; `jsonschema` dep avoided to keep the lockfile lean)

## 15. Deployment Artifacts

- [x] 15.1 Author `Dockerfile` with `python:3.12-slim`, non-root user `privaci` (UID 10001), bundled SpaCy model
- [x] 15.2 Verify image size ≤ 600 MB
- [x] 15.3 Verify image runs read-only and writes only to `/tmp`
- [x] 15.4 Author `docker-compose.yml` with sample source PG + empty target + engine
- [x] 15.5 Generate small synthetic seed dataset (~1 MB, never any real PII) for demo
- [x] 15.6 Author Helm chart skeleton (Chart.yaml, values.yaml, templates/)
- [x] 15.7 Helm: CronJob + Secret refs + ConfigMap + securityContext
- [x] 15.8 Lint Helm chart with `helm lint`, `kubeval`, `kube-score`
- [x] 15.9 Set up multi-arch container build (`linux/amd64`, `linux/arm64`)
- [x] 15.10 Add SBOM generation (`syft`) and image signing (`cosign`) to release CI
- [x] 15.11 Publish chart to OCI registry as part of release CI
- [x] 15.12 Define release channels so the commercial layer can track a stable
      contract (see ADR-0007 "Compatibility commitments"):
  - [x] 15.12.1 Beta channel: `vX.Y.Z-beta.N` tags off `main`, published as
        GitHub **pre-releases** + a `:beta` / `:edge` image tag
  - [x] 15.12.2 Stable channel: `vX.Y.Z` tags published as GitHub Releases +
        `:X.Y.Z`, `:X.Y`, `:latest` image tags. Stable is the only channel the
        Marketplace image is built from — never `main` or a beta
  - [x] 15.12.3 Document the channel policy + cadence in `docs/deployment.md`
- [x] 15.13 Make `CONTRACT_VERSION` machine-discoverable for downstream pinning:
  - [x] 15.13.1 Stamp `org.opencontainers.image.version` and a
        `io.boundarylogic.contract_version` OCI label on every published image
  - [x] 15.13.2 Expose `privaci --contract-version` (prints
        `privaci.contracts.CONTRACT_VERSION`) so consumers can assert compatibility
  - [x] 15.13.3 Add a CI check that fails the release if `CONTRACT_VERSION`'s
        major does not match the engine's major version

## 16. Vertical Config Packs Infrastructure

- [ ] 16.1 Create `boundarylogic/config-packs` repo (separate from engine)
- [ ] 16.2 Define pack manifest format and Ed25519 signing process
- [ ] 16.3 Author HIPAA starter pack (patient_id, mrn, npi, diagnosis_code patterns)
- [ ] 16.4 Author PCI-DSS starter pack (card_number, cvv, billing_address)
- [ ] 16.5 Author GDPR starter pack (EU-specific identifiers)
- [ ] 16.6 Document `CONTRIBUTING.md` for community pack submissions
- [ ] 16.7 Wire engine's `install-pack` to fetch from default registry URL

## 17. Documentation & First-Run Experience

- [x] 17.1 Author docs site scaffold (e.g., `mkdocs-material`) under `docs/`
- [x] 17.2 Quickstart page: copy-pasteable from zero to first masked row
- [x] 17.3 Configuration reference auto-generated from JSON Schema
- [x] 17.4 CLI reference auto-generated from `typer`
- [x] 17.5 Architecture overview page summarizing `design.md`
- [x] 17.6 "Building a PrivaCI plugin" page (contracts module)
- [x] 17.7 Per-module `README.md` files per `.cursorrules` §6
- [x] 17.8 Author security disclosure policy (`SECURITY.md`)

## 18. Public Beta Release Gate

- [x] 18.1 Verify all CI gates green: black, isort, ruff, mypy strict, pytest ≥85%, pip-audit
- [x] 18.2 Verify security-critical modules at 100% coverage
- [x] 18.3 End-to-end test on a representative 1 GB Postgres dataset
      (server-side fixture, bounded-memory streaming proven; exposed and fixed
      a 24-bit UNIQUE-suffix birthday collision)
- [x] 18.4 End-to-end test on a cyclic-FK schema
- [x] 18.5 End-to-end test on a polymorphic-FK schema (warning emitted, run succeeds)
- [x] 18.6 Resume test: kill -9 mid-run, restart with `resume`, verify zero data loss/duplication
- [x] 18.7 Documentation scrub before the repo goes public (see ADR-0007
      "Documentation & repository placement"):
  - [x] 18.7.1 Remove business/GTM material: `proposal.md` and the GTM/business
        sections of `openspec/changes/init-privaci-engine/proposal.md`
  - [x] 18.7.2 Move commercial-only ADRs out of the public repo:
        `docs/adr/0003-billing-dimension-source-dbs.md` (relocated to
        `privaci-commercial`; public repo keeps a tombstone)
  - [x] 18.7.3 Confirm engine ADRs (masking, streaming, memory model, salt UX,
        FK strategy, partitioning, ELv2) remain public for auditability
  - [x] 18.7.4 Grep docs/ for pricing, tier, or competitor references and relocate
        them to `privaci-commercial`
  - [x] 18.7.5 Verify `docs/README.md` and root `README.md` link only to
        public-facing pages after the scrub
  - [x] 18.7.6 Git history scrub: no personal emails in author/committer fields
        *or* commit message bodies (including `Co-authored-by:` trailers from
        squash-merges). Use `git filter-repo` with a mailmap and
        `--replace-message` if needed; set local `user.email` to GitHub noreply;
        enable GitHub **Keep my email addresses private** and **Block
        command-line pushes that expose my email**. Automated guard:
        `scripts/check_git_emails.py` (CI); runbook:
        `docs/runbooks/git-history-privacy.md`.
  - [x] 18.7.7 Confirm no personal emails remain reachable on GitHub: closed PRs
        keep old commit SHAs alive via `refs/pull/*` even after a history rewrite.
        Before public launch, either publish from a fresh repo with clean history
        or ask GitHub Support to garbage-collect cached views. Documented in the
        git-history privacy runbook; automated scan passes on current history.
  - [x] 18.7.8 Apply the placement policy to `openspec/` artifacts: the public
        repo's `openspec/changes/` and specs contain engine changes only.
        Commercial changes (the former §19–22 lineage, now `add-commercial-layer`)
        belong in `privaci-commercial`; website changes (`add-marketing-site`,
        `add-docs-ai-assistant`) belong in `boundarylogic-web`. Verify no GTM/
        pricing/tier/competitor content remains in any committed proposal or spec.
- [x] 18.8 Tag `v0.1.0-beta.1`, publish image + chart, announce
  - [x] 18.8.1 Provision the config-pack trust anchor for the release: generate
        the Ed25519 keypair, keep the private key in release secrets, publish the
        public key in the release notes, and ship it to runtimes via
        `PRIVACI_PACK_PUBLIC_KEY` (see `docs/runbooks/pack-signing.md`). The
        engine ships no embedded key; `scripts/check_pack_key.py` gates this.
        Helper: `scripts/generate_pack_signing_key.py`.

## 19–22. Commercial layer, Marketplace, drift, commercial GA — moved

The commercial implementation roadmap (commercial layer, AWS Marketplace listing,
drift detection, and the commercial GA gate) is tracked in the private
`privaci-commercial` repository, not in this public engine repo (ADR-0007;
§18.7.8). The public engine only declares the `commercial-tier-contract` ABCs and
ships no-op fallbacks; see the `commercial-tier-contract` capability spec.

## 23. MedicalHelpDesk Corp test fixture (Tier 1 + Tier 2)

- [x] 23.1 Create `tests/fixtures/demo_corp/` package skeleton with `schema.py`, `seed.py`, `generate.py`, providers/, tiers.py
- [x] 23.2 Implement `schema.py` — DDL as Python for all four schemas: `public`, `clinical`, `auth`, `audit_internal`
- [x] 23.3 Implement deterministic `seed.py` (`Faker.seed_instance(42)`, `random.seed(42)`, hard-assertion guard against real-PII imports)
- [x] 23.4 Implement provider modules: `orgs.py`, `users.py`, `patients.py`, `visits.py`, `tickets.py`, `messages.py`, `events.py`
- [x] 23.5 Implement narrative-prose generator for `ticket_messages.body` and `patient_visits.visit_notes` (templated, mentions Faker-generated names/dates/MRNs for L2 NER bait)
- [x] 23.6 Implement `generate.py` CLI: `--tier {mini,demo,stress}`, `--scale`, `--out`
- [x] 23.7 Generate and commit **mini** tier SQL at `tests/fixtures/sql/demo-corp/` (full **demo** tier on-demand via `--tier demo`, not committed)
- [x] 23.8 Author `Makefile` targets: `fixtures-generate`, `fixtures-verify` (diff committed vs regenerated)
- [x] 23.9 Pre-commit hook `verify-fixtures` that fails if committed SQL is stale
- [x] 23.10 Implement Tier 1 pytest fixtures in `tests/conftest.py` and `tests/fixtures/builders.py` (in-memory per-test minimal schemas)
- [x] 23.11 Author `tests/integration/assertions.py` helper: `assert_no_pii_present()`, `all_fks_valid()`, `audit_count()`, `partition_count()`, etc.
- [x] 23.12 Author edge-case SQL fixtures at `tests/fixtures/sql/edge-cases/`: `non-deferrable-cycle.sql`, `no-primary-key.sql`, `unsupported-types.sql`, `permission-denied.sql`, `dangling-fk-exclude.sql`, `composite-pk-only.sql`
- [x] 23.13 Author reference configs: `tests/fixtures/configs/demo-corp.yaml`, `minimal.yaml`, `strict.yaml`
- [x] 23.14 Author `compose.dev.yml` (long-running source + target Postgres for dev) and update `compose.yml` (demo with engine) to load `demo-corp` fixtures
- [x] 23.15 End-to-end integration test that runs `privaci run` against Demo Corp and verifies the full assertions module
- [x] 23.16 Author `docs/test-fixtures.md` (already drafted) and wire links from `docs/local-development.md` and the root README

## 24. PostgreSQL native partitioning support

- [x] 24.1 Extend `privaci.catalog` introspection to query `pg_partitioned_table`, `pg_inherits` and populate `is_partitioned`, `partition_strategy`, `partition_key`, `partition_children` on `TableInfo`
- [x] 24.2 Record per-child `parent_partition` and `bound: 'FOR VALUES ...'` strings
- [x] 24.3 Pre-flight check that rejects sub-partitioning (a partition that is itself partitioned) with exit `2`
- [x] 24.4 Pre-flight FK-graph treatment: parent edges only (no per-child FK duplicates)
- [x] 24.5 Schema replication: emit `CREATE TABLE <parent> ... PARTITION BY <strategy> (<keys>)` followed by `CREATE TABLE <child> PARTITION OF <parent> <bound>` per partition
- [x] 24.6 Config validation: reject per-partition `strategy` overrides with exit `3`
- [x] 24.7 Streaming: enqueue partition children as independent streaming units (parent has no rows, not streamed)
- [x] 24.8 Target-side direct-COPY into each child (bypass parent tuple routing)
- [x] 24.9 Masking pipeline: resolve column config from the parent for every child
- [x] 24.10 Checkpoint per partition child in `_privaci.table_checkpoints`
- [x] 24.11 Emit `new_table` audit event with `reason: 'new_partition'` for partitions added between runs
- [x] 24.12 Integration tests against Demo Corp `raw_events` (24 range partitions) and `patient_visits` (4 list partitions)
- [x] 24.13 Integration test: crash mid-partition, verify resume restarts only the affected partition

## 25. Implied (soft) FK detection

- [x] 25.1 Extend `postgres-catalog` pattern detector to flag column-name implied FKs (`*_email`, `*_username`, `*_user_id`, `*_mrn` matching another table's UNIQUE column)
- [x] 25.2 Emit `implied_fk_warning` events with a suggested `seed_alias` line
- [x] 25.3 Implement `config.implied_fk_ignore` list for user-silenced warnings
- [x] 25.4 Integration test against Demo Corp `clinical.patient_documents.*_email` columns
- [x] 25.5 Document the `seed_alias` mitigation pattern in `docs/configuration.md`

## 26. Views + identity columns (small but real)

- [x] 26.1 Catalog: enumerate views from `pg_views` and materialized views from `pg_matviews`
- [x] 26.2 Schema replication: skip views and matviews; emit `skipped_object` audit events
- [x] 26.3 Catalog: detect `GENERATED ALWAYS/BY DEFAULT AS IDENTITY` and distinguish from `SERIAL`
- [x] 26.4 Schema replication: emit identity DDL preserving `ALWAYS` vs `BY DEFAULT`
- [x] 26.5 Schema replication: post-load `setval` on the identity-owned sequence
- [x] 26.6 Integration tests for both views and IDENTITY behavior

## 27. Post-MVP (out of scope, captured for future changes)

- [ ] 27.1 _Future change:_ MySQL support
- [ ] 27.2 _Future change:_ SQL Server support
- [ ] 27.3 _Future change:_ PDF compliance report rendering
- [ ] 27.4 _Future change:_ Data subsetting (`sample_rate`)
- [ ] 27.5 _Future change:_ `append` strategy + per-table conflict policy
- [ ] 27.6 _Future change:_ Azure Marketplace listing
- [ ] 27.7 _Future change:_ Mongo / NoSQL sources
- [ ] 27.8 _Future change:_ Horizontal multi-node sharding
- [ ] 27.9 _Future change:_ Sub-partitioned tables (multi-level)
- [ ] 27.10 _Future change:_ Per-partition config overrides
- [ ] 27.11 _Future change:_ Value-distribution-based implied-FK discovery (commercial)
