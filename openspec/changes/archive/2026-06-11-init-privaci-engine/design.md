## Context

PrivaCI is greenfield. At the time of this change the repository contained the
original product proposal (since relocated to the private `privaci-commercial`
repo per ADR-0007), `.cursorrules` (Python 3.12 development standards), and an
empty OpenSpec workspace. No code, no language pinned in code, no schema, no
Dockerfile, no CI. Every architectural decision is still open.

This change is the foundation. It establishes the entire MVP architecture
and the public/commercial code split that everything afterwards builds on.
Decisions made here are load-bearing — getting them wrong means a rewrite,
not a refactor. They are documented exhaustively here and mirrored as ADRs
under `docs/adr/` so the rationale survives even if this change is later
archived.

**Constraints driving the design:**

- **Small team, tight scope.** No room for premature optimization or large
  up-front frameworks.
- **`.cursorrules` discipline:** Python 3.12+, asyncio for I/O, strict
  pydantic, ≤40-line functions, ≤400-line files, ≤cyclomatic-8,
  85% / 100% test coverage, `mypy --strict`, `ruff`, `black`.
- **Data never leaves the VPC.** PII in the container's memory, never on
  disk, never in logs, never to a third-party server.
- **CI/CD ergonomics:** the container is a one-shot job. It must boot
  fast, run deterministically, and exit cleanly. No daemons, no UIs.
- **Bounded resource use.** The engine cannot consume customer compute
  unbounded. Streaming must be constant-memory regardless of source size.

## Goals / Non-Goals

**Goals:**

- Stream-mask a 100 GB PostgreSQL database in constant memory.
- Preserve referential integrity across all FKs without a tracking DB.
- Boot to first masked row in under 30 seconds.
- Resume from a per-batch checkpoint after a crash.
- Produce a structured audit log per run, queryable via SQL.
- Make the public engine fully self-hostable and useful on its own.
- Make the commercial layer's extension points stable enough that the
  public engine can be released and iterated without breaking the
  commercial build.

**Non-Goals:**

- Real-time CDC.
- Multi-database-engine parity in MVP — PostgreSQL only.
- Horizontal scale-out — single-container MVP.
- Per-row Marketplace metering.
- A web UI or dashboard.
- A managed-service offering. (The ELv2 license prohibits offering the
  engine as a competing managed service.)

## Decisions

### D1. Runtime: Python 3.12

**Decision:** Python 3.12 with `asyncio`, `asyncpg`, `pydantic`, `typer`,
`spacy`. Container base image `python:3.12-slim`. Non-root user.

**Alternatives considered:**

- **Go:** ~20 MB binary, sub-second cold start, excellent `pgx` driver.
  Disqualified by SpaCy. Go has no production-grade equivalent — `prose`
  is too basic, `gobert` requires ONNX/cgo fragility, `spago` lacks model
  coverage. Re-implementing L2 NER in Go would be a multi-month project
  with weaker results.
- **Hybrid (Go core + Python NER sidecar):** Best raw performance.
  Disqualified by operational complexity. Two processes in one container,
  IPC overhead, deployment complexity.
- **Rust (`pyo3` extension):** Considered for the streaming hot path.
  Deferred to a possible v1.5 optimization if `asyncpg` + COPY-binary
  benchmarks fall below 50k rows/sec on representative loads.

**Rationale:** SpaCy is the single feature that picks the language.
Python's masking-library ecosystem (Faker, regex, presidio for reference)
and async DB ecosystem (asyncpg) are mature. The cold-start penalty
(~1–2 s) is irrelevant for a batch job that runs for minutes. The
container-size penalty (~400 MB vs ~20 MB) is irrelevant for a batch job.

**Trade-off accepted:** Throughput likely caps at ~50–100k rows/sec for
L1-only tables, dropping under 10k rows/sec on tables where L2 NER runs
across many text columns. A benchmark spike confirms or invalidates this.

### D2. Streaming: COPY ... TO STDOUT (FORMAT BINARY) → in-process → COPY ... FROM STDIN (FORMAT BINARY)

**Decision:** Source-side `COPY ... TO STDOUT (FORMAT BINARY)` piped
through an in-process decoder, masker, re-encoder, into target-side
`COPY ... FROM STDIN (FORMAT BINARY)`. Both legs of the COPY pipe run
concurrently in the same asyncio event loop.

**Alternatives considered:**

- **`OFFSET / LIMIT` pagination:** Degrades quadratically on large
  tables. Disqualified.
- **Keyset pagination (`WHERE pk > last_seen ORDER BY pk LIMIT n`) + batch
  INSERTs:** Predictable performance, simple, works without superuser
  privileges, easy to checkpoint. Throughput ceiling ~10–20k rows/sec.
  Backup plan if COPY-binary proves problematic.
- **PostgreSQL logical replication / `pg_logical`:** Would give CDC for
  free. Out of scope — the product is batch by design, and logical
  replication requires `wal_level=logical` on the source which many
  managed Postgres tiers (AWS RDS at lower tiers) do not enable.
- **`pg_dump` + restore + post-mask:** Cannot mask in-flight; would
  require staging unmasked data to disk, violating the "no intermediate
  data on disk" security guarantee.

**Rationale:** `COPY` is PostgreSQL's fastest path, ~10–50× faster than
batched INSERTs for bulk load. Binary format avoids text-encode/decode
overhead and preserves type fidelity (especially for `bytea`, `numeric`,
`timestamptz`). In-process row mutation between the two COPY pipes keeps
memory constant — exactly one batch (10k rows by default) ever in RAM.

**Trade-off accepted:** The binary protocol decode/encode is non-trivial
(see PostgreSQL's `src/backend/utils/adt/copy.c`). We use the
documented protocol; `asyncpg` exposes `copy_to`/`copy_from` at the
streaming level. A pure-Python binary codec is implemented for the
types we support; unsupported types fall through to text-mode COPY.

### D3. FK strategy: topological sort + DEFERRABLE constraints

**Decision:**

1. After catalog introspection, build the FK dependency graph.
2. Topologically sort tables; load roots first, leaves last.
3. For cycles: detect, then break by selecting the lowest-cost edge to
   defer (heuristic: nullable FK with smallest expected referencing-row
   count). Wrap the affected tables' load in a single transaction with
   `SET CONSTRAINTS ALL DEFERRED`.
4. Self-referential FKs are handled the same way (single-table cycle).
5. **Polymorphic / "soft" FKs** (e.g., `commentable_type` + `commentable_id`)
   cannot be discovered from catalogs. They are a documented limitation;
   the audit log emits a warning when a column matching common
   polymorphic patterns is detected without an inbound catalog FK.

**Alternatives considered:**

- **Disable triggers + foreign keys, load, re-enable:** Faster but
  requires superuser-equivalent privileges most managed Postgres tiers
  don't grant. Disqualified for portability.
- **Two-pass load (first pass nulls out FKs, second pass updates):**
  Doubles the row writes. Pessimistic memory model. Disqualified.

**Rationale:** Topo-sort handles 95% of real schemas (acyclic). Deferred
constraints handle the cycle case without privilege escalation. The
documented polymorphic-FK limitation is honest about what catalogs can
and can't see.

### D4. State storage: `_privaci` schema in the target database

**Decision:** All run state — `runs`, `table_checkpoints`, `audit_log` —
lives in a `_privaci` schema created in the target database on first
run. The schema is owned by PrivaCI; customers should not write to it.

**Alternatives considered:**

- **S3 / Azure Blob:** External dependency, breaks air-gapped deployments,
  another set of credentials to manage. Disqualified.
- **Redis / managed KV:** Another moving part for a batch job that
  already needs two DB connections. Disqualified.
- **Container-local SQLite:** State dies with the container. Resumability
  impossible for CI/CD runs (every job starts in a fresh container).
  Disqualified.
- **Source database:** Read-only by policy. Disqualified.

**Rationale:** The target database is the one resource we have guaranteed
write access to. Co-locating audit data with the masked data it describes
is operationally clean — the customer's auditor queries one place.
Resumability "just works" across container restarts. No new dependencies.

**Trade-off accepted:** The target DB must grant `CREATE SCHEMA`. This is
the only meaningful permission requirement beyond DML and is documented
in the quickstart.

### D5. Resumability: per-batch (every 10k rows) checkpoints

**Decision:** Each batch commit (default 10k rows) atomically writes the
last primary-key value to `_privaci.table_checkpoints`. On resume, the
engine reads the checkpoint and re-streams from `WHERE pk > last_pk_value`.

**Alternatives considered:**

- **Per-row checkpointing:** Negligibly safer, kills throughput by 10–50×.
  Disqualified.
- **Per-table only (no mid-table checkpoint):** A 4-hour table that
  crashes at hour 3 restarts from zero. Doesn't satisfy the
  "resumability is a selling point" requirement.
- **No resumability in MVP:** Cheapest, but undercuts a marketing claim
  and creates support pain on every transient network blip.

**Rationale:** One extra write per 10k masked rows is ~0.01% overhead.
Restart latency goes from "start over" to "lose at most 10k rows of
work." This is the right point on the cost/benefit curve.

**Constraint:** Resumability requires a stable, single-column primary
key. Tables with composite or non-monotonic keys fall back to a
table-level checkpoint (table done / not done). The audit log records
which strategy was used per table.

### D6. Salt UX: user-supplied, fail loudly if missing

**Decision:** Resolution order — `--salt` flag → `ANONYMIZATION_SALT` env
var → `config.global_salt` → secret URI in config. No silent fallback.
Engine exits with code 4 and a one-line setup command if unset. Minimum
length 32 characters, validated at boot.

`privaci gen-salt` is provided to make first-run trivial:

```bash
privaci gen-salt > .privaci-salt
chmod 600 .privaci-salt
```

**Alternatives considered:**

- **Default salt derived from cluster ID / source DB URL:** Convenient,
  but the salt silently changes when infrastructure rotates (terraform
  refresh, blue/green migration, RDS endpoint change). Determinism is
  silently broken; tests start failing for unrelated reasons. Strongly
  rejected after considering the failure mode.
- **Auto-generated salt persisted in `_privaci.runs`:** Customer never
  sees the salt; if `_privaci` schema is dropped, all deterministic
  fakes change. Strongly rejected — the customer must own the salt.

**Rationale:** The salt is functionally a secret. Customers manage their
own secrets, in their own secret store, against their own rotation
policy. Engine guarantees: it is loud about missing salts, validates
length, and never logs the salt value.

### D7. Secrets via URI resolver

**Decision:** Any string field that accepts a secret may use a URI:

- `aws-sm://<secret-id>[?region=...&key=...&version=...]`
- `azure-kv://<vault>/<secret>[?version=...]`
- `vault://<mount>/<path>#<key>`
- `env://VAR_NAME`
- `file:///run/secrets/db-pass`
- Literal `postgres://...` — accepted, for dev convenience.

Resolution happens once at boot. Secret values are wrapped in a
`SecretStr` type that redacts on `__repr__` and `__str__`. A
centralized logging filter strips known secrets from log records.

**Alternatives considered:**

- **Env vars only:** Simplest. Forces customers to wire AWS Secrets
  Manager → env var manually, which is the most error-prone path. The
  URI scheme makes Marketplace customers a one-line change. Worth the
  ~200 lines of resolver code.

### D8. Target conflict policy: fail by default

**Decision:** Pre-flight checks the target. If any user-table exists,
the engine exits with code 2 unless `on_existing_data` overrides:

- `fail` (default) — safe.
- `truncate` — `TRUNCATE` all in-scope target tables in dependency order.
- `drop_create` — `DROP TABLE ... CASCADE` and re-clone DDL from source.
  Use when source schema has evolved.
- `append` — v1.x. Requires per-table conflict policy (UPSERT keys etc.).

Tables in the `_privaci` schema are exempt from the "is empty" check.

**Rationale:** Default-safe. Customers who want destructive behavior must
opt in explicitly. Helps prevent the "I ran it against my real staging
DB and it wiped it" failure mode that has killed similar tools.

### D9. Deterministic faker: salt + hash, UNIQUE-aware

**Decision:** For each maskable column, the faker selects a fake value by:

```
seed   = sha256(salt || column_path || normalized_input).digest()[:16]
index  = int.from_bytes(seed, 'big') % len(fake_library)
fake   = fake_library[index]
```

`column_path` includes table+column so the same input email in different
columns produces different fakes (preventing trivial cross-correlation).

**UNIQUE constraint handling:** If the column is part of a UNIQUE
constraint (discovered by `postgres-catalog`), the faker switches to:

```
fake = base_fake + '+' + base16(seed)[:6]
```

Preserving uniqueness while keeping determinism.

**Alternatives considered:**

- **Pure deterministic without UNIQUE awareness:** Easy to implement,
  guaranteed to cause UNIQUE-constraint violations at scale (a 1M-row
  emails table colliding into a 10k-element fake library).
- **Pre-generate a per-run lookup table:** Effectively re-creates a
  tracking database, which the proposal explicitly avoids.

**Rationale:** The catalog already knows about UNIQUE constraints. Using
that knowledge to auto-switch strategies is a "just works" moment that
customers don't have to configure.

### D10. License: ELv2 for the public engine

**Decision:** The public repository (`privaci`) is licensed under the
Elastic License 2.0 (ELv2). This permits self-hosting, reading, forking,
internal use, and contribution; it prohibits offering PrivaCI as a
hosted or managed service in competition with the maintainer.

**Alternatives considered:**

- **BSL (Business Source License):** Time-limited proprietary that
  converts to a FOSS license after N years. Adds legal surface (must
  specify conversion date, jurisdiction, additional grant). Customers
  must reason about post-conversion terms. No net benefit over ELv2 for
  the maintainer's actual threat model.
- **FSL (Functional Source License, Sentry):** BSL refined to two-year
  conversion-to-Apache. Cleaner than BSL but still introduces
  conversion semantics. Defensible second choice if ELv2 ever fails
  customer legal review.
- **AGPL:** Would not stop the threat (a managed-service competitor
  willing to release their service code). Disqualified.
- **Apache 2.0:** No protection against managed-service competition.
  Disqualified.
- **Pure closed source:** Sacrifices the "in-VPC, source-available,
  auditable" trust signal that is central to the security pitch.
  Disqualified.

**Rationale:** The product *requires* customer self-hosting (data never
leaves their VPC). A license that prohibits self-hosting prohibits the
product. ELv2 prohibits only the one threat we actually want to block:
a competitor offering PrivaCI-as-a-Service. Customer legal teams
already know ELv2 (Elastic, Redis Labs, Sentry). Procurement is fast.

**Trade-off accepted:** Some OSI-purist communities will label
"source-available" as "not open source." This is technically correct
but rarely a concern for the operators who self-host the engine.

### D11. Public / commercial split

**Decision:** Two repositories.

**Public (`privaci`, ELv2):** Streaming engine, COPY pipeline, catalog,
schema replication, L1 + L2 masking, deterministic faker, audit log,
resumability, auto-detect, config, CLI (`run`, `dry-run`, `validate`,
`gen-salt`, `generate-ci`, `install-pack`, `migrate-config`, `resume`),
Helm chart, Dockerfile, Compose stub.

**Private (`privaci-commercial`, proprietary):** AWS Marketplace
metering, license-key validation, source-DB counting, L3 LLM connectors
(Bedrock, Azure OpenAI), drift detection, signed compliance reports,
Slack/webhook notifier, AWS Marketplace listing assets.

The commercial layer plugs in via Python ABCs declared in
`privaci.contracts.*`. Without the commercial layer installed, the
public engine runs in "community mode" — L3 is unavailable, no
metering, no license check, no Slack notifier. Everything else works.

**Alternatives considered:**

- **One repo with paywalled directories:** Confusing license model,
  invites accidental redistribution of commercial code.
- **True open-core with a community fork:** Brutal to maintain alone.
  Rejected.

**Rationale:** The split is clean. Community users get a real product.
Commercial value is in plumbing (metering, license, LLM connectors,
reports) — high-cognitive-load features customers expect to pay for.

### D12–D13. Billing dimension & AWS Marketplace SKU — moved

The billing-dimension design (how source databases are counted for metering) and
the AWS Marketplace SaaS Contract decision are commercial business-model material
and live in the private `privaci-commercial` repository (ADR-0007; §18.7). The
engine's `source_db_hash` itself is documented with the `state-and-audit`
capability; its use as a billing dimension is commercial.

### D14. L3 LLM connector: commercial-only

**Decision:** Level 3 (BYO-LLM) connectors live entirely in the private
repo. The public engine ships a Python ABC (`LLMConnector`) and a
no-op fallback. If a column's config references `ai_refine` and no
commercial layer is installed, the engine fails at config-validation
time with a clear message.

**Alternatives considered:**

- **Ship L3 in the public engine:** Highest support cost (auth, retries,
  rate limits, model deprecation) is on the maintainer for free.
  L3 is also where hallucination risk is highest. Paid-support gating
  protects both sides.

**Rationale:** L1 + L2 are already enormously valuable on their own
(regex + local NER, no external calls). L3 lives in the commercial layer
because its operational cost (auth, retries, model lifecycle) and support
burden belong with the paid offering.

### D15. Compliance reports: signed JSON in v1

**Decision:** `privaci report --run <run_id>` (commercial) emits a
deterministically structured JSON document with a detached signature
(Ed25519 over the canonical-encoded payload). PDF rendering deferred to
v1.1.

**Rationale:** JSON-first is faster to ship, easier to test, more
machine-readable. The signature is the actual moat — auditors care that
the report wasn't tampered with. Pretty PDFs are a v1.x polish.

### D16. Auto-detect default: ON, strict mode opt-in

**Decision:** Auto-detection runs by default in addition to YAML config.
Detected columns not covered by config are masked using the inferred
provider, and the audit log records both the detection and the action.

Strict mode (`--strict-autodetect`) fails the run when an unrecognized
column is found in a table where config exists but doesn't cover the
column. Used by mature customers who treat config as a contract.

**Rationale:** Day-one experience must be "drop in, get masked output."
Strict mode is the day-90 experience for compliance-anxious teams.

### D17. Audit log: always on

**Decision:** `_privaci.audit_log` is written for every run, by
default. `--no-audit-table` exists for the rare customer who treats the
target database as read-by-tests-only.

**Rationale:** Audit data is the foundation of the compliance-report
moat. It also gives the customer's auditor a SQL-queryable history of
PII handling. The cost is one row per (table, column, action) per run —
trivial.

### D18. Container model: one-shot job

**Decision:** The container runs to completion and exits. No daemon.
Exit codes:

- `0` — success
- `1` — generic error (logged with stack trace)
- `2` — pre-flight failure (target not empty, schema mismatch)
- `3` — config validation failure
- `4` — missing salt
- `5` — license / Marketplace entitlement failure (commercial only)
- `6` — drift detected (commercial only)

**Rationale:** Matches the CI/CD workflow. Composes cleanly with K8s
CronJobs, ECS scheduled tasks, GitHub Actions runners. Avoids the
operational complexity of a long-running service.

### D20. PostgreSQL native partitioning: clone parent + stream per child

**Decision:** The engine supports PostgreSQL declarative partitioning
(`PARTITION BY RANGE / LIST / HASH`) in MVP. The approach is:

- **Catalog:** detect partitioned parents and their children; record
  partition strategy, key column list, and per-child bound
  expressions.
- **Schema replication:** create the parent first with its `PARTITION
  BY` clause, then create each child with its `PARTITION OF
  <parent> <bound>` clause.
- **Streaming:** each partition child is its own streaming unit. The
  parent has no rows of its own and is not streamed. The masking
  pipeline applies the parent's column config to every child.
- **Resumability:** each partition child gets its own row in
  `_privaci.table_checkpoints`. A crash mid-partition resumes
  only that child.
- **Out of scope for MVP:** sub-partitioning (a partition that is
  itself partitioned). Pre-flight rejects this with exit `2`.
- **Out of scope for MVP:** per-partition config overrides. The
  parent's config governs all children.

**Alternatives considered:**

- **Stream from the parent only, rely on Postgres tuple routing on
  target:** Simpler, but checkpoint granularity becomes the entire
  partitioned table — a 5M-row 24-partition table that crashes at
  partition 23 would restart all 24. Rejected.
- **Treat the partitioned parent as a single virtual table:** Lies
  about reality. The catalog already distinguishes parents from
  children; we should honor that.
- **Defer partitioning to v1.x:** Real customer schemas in 2026
  routinely use native partitioning for events / audit /
  time-series tables. Telling early customers "we don't handle
  your `events` table yet" is a non-starter.

**Rationale:** Per-child streaming is more code, but each piece is
simple (a partition is just a table from streaming's point of view).
The dependency-graph code only needs a small "skip the parent of an
edge if it's partitioned" rule. The big win is that checkpointing
granularity stays at the same per-batch level customers expect for
non-partitioned tables.

### D19. Vertical config packs: separate community-contributable repo

**Decision:** Config packs live in `boundarylogic/config-packs`, a separate
public repo with permissive license (MIT or CC-BY) on the YAML files.
`privaci install-pack <name>` fetches and merges into the local
`mask-rules.yaml`, with a preview prompt.

**Rationale:** Each pack is also a content-marketing artifact ("HIPAA
staging in 10 minutes"). Community-contributable means experts in
specific regulated industries can validate and improve rules. Separating
the repo keeps the engine's release cadence independent from rule
updates.

## Risks / Trade-offs

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|------------|--------|------------|
| R1 | L2 SpaCy throughput < 10k rows/sec on text-heavy tables | M | H | Early benchmark spike. If true, batch text columns into multi-row SpaCy calls; consider `nlp.pipe(batch_size=...)`. Last resort: drop SpaCy from MVP, ship L1-only with auto-detect compensating. |
| R2 | COPY-binary protocol edge cases (rare types: PostGIS, custom domains) | M | M | Fall back to text-mode COPY per-table when binary encode fails. Audit log records the fallback. |
| R3 | FK cycles needing deferred constraints in a non-DEFERRABLE schema | L | M | Detect at pre-flight; emit a SQL snippet the customer can run to convert constraints to `DEFERRABLE`. Fail the run with the snippet in the error. |
| R4 | Auto-detect false negatives (PII column missed) | M | H | Strict mode + dry-run report listing "columns I'm masking, columns I'm passing." Continuous improvement of the pattern library. ELv2 license means the engine source is auditable. |
| R5 | Auto-detect false positives (masking a non-PII column breaks tests) | H | M | Dry-run preview; per-column override (`action: passthrough`) supported in YAML; documented common cases. |
| R6 | Customer loses salt → all deterministic fakes change | L | H | `privaci gen-salt` documentation emphasizes salt storage. Engine refuses to start without a salt. Audit log records salt fingerprint so the customer can detect rotation. |
| R7 | Source schema has polymorphic and/or implied (soft) FKs the catalog can't see | H | M | Two-tier detection: (a) polymorphic pattern (`*_type` + `*_id` paired columns) emits `polymorphic_fk_warning`; (b) implied-FK pattern (`*_email`/`*_username`/`*_user_id`/etc. on one table matching a UNIQUE column on another) emits `implied_fk_warning` with a suggested `seed_alias` line the user can paste into config. Both warnings are non-blocking; user can silence individual columns. Value-distribution-based discovery (column X's values overlap UNIQUE column Y's values) is deferred to v1.x and is a natural fit for the commercial drift detector. |
| R8 | _(commercial)_ AWS Marketplace contract-terms risk | — | — | Commercial concern — tracked in `privaci-commercial` (strategy doc). |
| R9 | A 4-hour job crashes; resume picks up wrong batch because source rows changed | M | M | Resumability is per-batch with a `source_db_hash` and `config_hash` recorded on the run. Resume only works for the same (source, config). Otherwise: fail-loud, request `--force-restart`. |
| R10 | `_privaci` schema permissions denied | L | H | Pre-flight checks for `CREATE SCHEMA` privilege; fail with clear error directing the customer to grant it. |
| R11 | Memory pressure when masking very wide tables (1000+ columns) | L | M | Batch size auto-tunes down based on row size. Hard cap at 1 GB total batch memory. |
| R12 | _(commercial)_ Competitor forks the engine and rebuilds the commercial layer | — | — | Accepted; ELv2 forbids managed-service competition. Business-model mitigations tracked in `privaci-commercial` (strategy doc). |

## Migration Plan

This change introduces PrivaCI from zero, so there is no existing system
to migrate from. The "migration" is the implementation phasing — see
`tasks.md` — which sequences capabilities so each is usable in isolation:

1. Catalog + schema replication — produces a verified-empty target with
   the source DDL cloned. No data yet. Demonstrable.
2. Streaming pipeline + state schema — first end-to-end passthrough copy
   (no masking). Resumability validated by killing the container mid-run.
3. Deterministic faker — passthrough copy now masks one column with the
   salt-hashed faker. Cross-table FK consistency verified.
4. L1 regex + auto-detect — zero-config first-run experience demonstrable.
   First "drop in, get masked output" moment.
5. L2 SpaCy + YAML config — full MVP-class masking.
6. Docker / Compose / Helm + docs — public-beta-ready.
7. Commercial layer — tracked separately in `privaci-commercial` (ADR-0007).

Rollback strategy is implicit per phase: any incomplete capability is
opt-in via config, so the public-beta release can ship with whatever set
is complete.

## Open Questions

- **Q1.** Should pre-flight verify FK constraints on source are
  `DEFERRABLE` for cyclic schemas, or always attempt and let the
  database fail? — **Spike 2.3 (2026-05-29):** deferred insert/commit works
  when constraints are `DEFERRABLE INITIALLY DEFERRED`. **Decision:** pre-check
  + emit SQL snippet on failure (do not blind-attempt on production schemas).
- **Q2.** What's the right default `batch_size`? 10k rows is a sensible
  guess; benchmarks may refine to 5k or 50k. — **Spike 2.1:** COPY-binary
  passthrough is viable via `asyncpg`; row-level batch tuning still needs a
  wide-table benchmark during streaming implementation (§12).
- **Q3.** Should `_privaci.runs` retain history forever, or auto-prune
  after N runs? Probably retain everything for compliance, but offer a
  `privaci state prune --older-than 1y` admin command.
- **Q4.** Should `privaci gen-salt` write to a default location or
  always to stdout? Stdout-only is safer (no accidental commit); the
  documentation snippet uses redirection to a file the customer chooses.
- **Q5–Q6.** _(commercial)_ Open questions about AWS Marketplace metering timing
  and fail-closed behavior when the commercial layer cannot authenticate are
  tracked in `privaci-commercial` (strategy doc).
