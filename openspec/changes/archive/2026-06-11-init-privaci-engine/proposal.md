## Why

Engineering teams need realistic staging data for development, testing, and CI but
production data is full of PII. Existing options have significant drawbacks:
enterprise tools require heavy procurement, SaaS APIs require streaming production
data to an external server, DIY scripts break on every schema migration, and many
open-source alternatives are unmaintained.

PrivaCI ships a stateless container that runs **inside the customer's own
VPC**, reads from a source database (typically a production replica), masks
PII with a three-tier pipeline, and writes realistic synthetic data to a
target staging/dev database with full referential integrity preserved. No
data ever leaves the customer's network boundary.

> Pricing, tiers, and competitive positioning are business-model material and
> live in the private `privaci-commercial` repository, not this public engine
> repo (ADR-0007; §18.7).

This change establishes the MVP capability set, the public/commercial code
split, and the foundational architecture that all post-MVP work builds on.

## What Changes

### Product scope
- **In-VPC batch masking engine** for PostgreSQL — clone DDL, stream rows,
  mask PII, write to target. One-shot container, exits 0 on success.
- **Three-tier masking pipeline:** L1 deterministic regex rules, L2 local
  SpaCy NER (`en_core_web_sm`), L3 BYO-LLM connector contract (Bedrock /
  Azure OpenAI). **L3 implementation lives in the private commercial repo;
  the public engine ships L1 + L2 only.**
- **Zero-config auto-detection** of common PII columns (`email`, `phone`,
  `ssn`, `first_name`, `last_name`, `address`, `dob`, `ip_address`,
  `credit_card`, `password`, `token`). Produces a usable masked clone before
  any YAML is written. Strict mode optional.
- **Declarative YAML config** with strict pydantic + JSON Schema validation.
  Versioned; engine v2 reading a v1 config fails fast with a `migrate-config`
  hint.
- **Salt-hashed deterministic faking.** Same input + same salt always
  produces the same fake output, preserving FK relationships across tables
  without a tracking database. UNIQUE-aware: columns under UNIQUE
  constraints automatically switch to a collision-resistant strategy.
- **Per-batch resumability.** Checkpoints persist in a dedicated
  `_privaci` schema in the target database. A crashed 4-hour job resumes
  from the last 10k-row checkpoint, not from zero.
- **Audit log per run** stored in `_privaci.audit_log`. Tables masked,
  columns touched, PII detected but not covered by config. Foundation for
  the commercial compliance-report feature.
- **CI/CD-first packaging.** Docker image, Docker Compose stub for
  evaluation, Helm chart for production, `privaci generate-ci` subcommand
  that emits a ready-to-commit GitHub Actions / GitLab CI / K8s CronJob
  workflow with least-privilege IAM policy.
- **Vertical config packs** loadable from a separate public, community
  repository (`boundarylogic/config-packs` — HIPAA, PCI-DSS, GDPR starter packs).

### Security & operational guarantees
- **Stays inside the VPC.** No data ever leaves the customer's network.
  Even L3 LLM calls (when enabled) go via the customer's own IAM role to
  their own Bedrock or Azure OpenAI endpoint.
- **Salts are user-supplied.** Resolution order: `--salt` flag, env var,
  config field, secret URI. No silent default. Engine fails fast with a
  one-line setup command if no salt is configured. Minimum length 32
  characters, validated at boot.
- **Secrets via URI resolver chain:** `aws-sm://`, `azure-kv://`,
  `vault://`, `env://`, `file://`. Literal `postgres://` accepted for
  local dev only. Secret values never appear in logs or error output.
- **Target verified empty by default.** `on_existing_data: fail` is the
  default. `truncate` and `drop_create` strategies are explicit opt-ins.
- **PII never logged.** All log messages run through a redaction filter.
  Intermediate masked data never written to disk — in-memory streaming only.

### Code organization & licensing
- **Public repo (`privaci`, licensed under ELv2)** — the complete,
  self-hostable engine: streaming, catalog, schema replication, L1 + L2
  masking, deterministic faker, audit log, resumability, auto-detect,
  config, CLI, Docker / Compose / Helm packaging, vertical-config-pack
  loader, `generate-ci`, `migrate-config`.
- **Private repo (`privaci-commercial`, proprietary)** — thin layer
  baked into the official Marketplace image: AWS Marketplace metering,
  license-key validation, source-DB counting, L3 Bedrock/Azure OpenAI
  connectors, signed compliance reports, drift detection, Slack/webhook
  notifier. The public engine defines `commercial-tier-contract`
  extension points; the private layer implements them.
- **Source-database identity.** The engine computes a `source_db_hash` from the
  source connection for run identity and state. Its use as a *billing* dimension,
  along with metering and tier definitions, is commercial and lives in the private
  `privaci-commercial` repository (ADR-0007; §18.7).

### Non-goals (explicit out-of-scope for this change)
- MySQL and SQL Server support — v1.x.
- Schema drift detection (`privaci detect-drift`) — commercial, v1.x.
- Data subsetting (`sample_rate`) — commercial, v1.x.
- PDF compliance reports — v1.x (signed JSON in MVP).
- Mongo / non-relational sources — v2.x.
- Horizontal multi-node sharding — v2.x.
- Real-time CDC — never. PrivaCI is batch by design.

## Capabilities

### New Capabilities

- `engine-cli`: Command-line surface (`run`, `dry-run`, `validate`,
  `gen-salt`, `generate-ci`, `install-pack`, `migrate-config`, `resume`,
  `report`), exit codes, pre-flight checks, and overall run lifecycle.
- `postgres-catalog`: PostgreSQL introspection — tables, columns, types,
  primary keys, foreign keys. Builds the dependency graph, performs topo
  sort, detects cycles, surfaces polymorphic-FK limitations.
- `schema-replication`: Clones the source DDL into the target, including
  types, constraints, indexes (selective), and FK relationships. Honours
  per-table `strategy` (transform, exclude, empty, truncate).
- `streaming-pipeline`: PostgreSQL `COPY ... TO STDOUT (FORMAT BINARY)`
  source-side, in-process row decoder → masker → row encoder, `COPY ...
  FROM STDIN (FORMAT BINARY)` target-side. Batch sizing, backpressure,
  per-batch checkpoint commits, deferred constraints for FK cycles.
- `masking-pipeline`: Level 1 (deterministic regex rules) and Level 2
  (local SpaCy NER for `PERSON`, `ORG`, `GPE`, `LOC` entities). Defines
  the Level 3 extension contract used by the commercial connector.
- `deterministic-faker`: Salt-hashed deterministic synthetic value
  generation. Same input + same salt → same output across tables.
  UNIQUE-constraint awareness toggles a collision-resistant strategy.
- `auto-detect`: Pattern-based PII column scanner for first-run usability.
  Strict mode fails the run on uncovered columns; permissive mode emits a
  warning to stdout and the audit log.
- `config-yaml`: Strict pydantic models for `mask-rules.yaml`, JSON
  Schema export, version field, `extra=forbid`, helpful validation error
  messages, version-compatibility policy (fail with `migrate-config` hint).
- `secrets-resolver`: URI scheme resolver for `aws-sm://`, `azure-kv://`,
  `vault://`, `env://`, `file://`, literal `postgres://`. Centralized
  redaction so secret values never reach logs or exceptions.
- `state-and-audit`: The `_privaci` schema in the target database —
  `runs`, `table_checkpoints`, `audit_log`. Single source of truth for
  resumability, audit, and a stable `source_db_hash` for run identity.
  Created idempotently at run start.
- `observability`: JSON-lines stdout protocol for CI/CD consumption.
  Defined event types (run.start, table.start, table.progress, table.end,
  run.end, warning, error). Stable schema customers can parse.
- `deployment-artifacts`: Dockerfile (`python:3.12-slim`, non-root user),
  `docker-compose.yml` for local evaluation, Helm chart for production
  Kubernetes. All built and published via release CI.
- `commercial-tier-contract`: The public extension-point contract the
  closed commercial layer plugs into — license validator interface,
  metering hooks, L3 LLM-connector interface, report-renderer interface,
  notifier interface. Defines stable Python ABCs so the public engine
  remains usable without the commercial layer present.

### Modified Capabilities

_None — this is the foundational change. No existing specs._

## Impact

- **Code (new):** `src/privaci/` — the full Python package per the
  capabilities listed above. Estimated ~6,000 LOC for MVP.
- **Code (private repo):** `privaci-commercial/` — separate repo,
  estimated ~1,500 LOC for MVP commercial layer.
- **Dependencies (new, pinned via `pip-compile`):** `asyncpg`, `spacy`,
  `pydantic`, `pyyaml`, `typer`, `cryptography`, `boto3` (secrets +
  Marketplace), `azure-identity`, `azure-keyvault-secrets`, `hvac`
  (HashiCorp Vault). `en_core_web_sm` model downloaded during image build.
- **Infrastructure:** AWS Marketplace listing,
  `boundarylogic/config-packs` public repo, container registry (GHCR or ECR
  Public), Helm chart repo (`charts.boundarylogic.io`), documentation site
  (`boundarylogic.io`).
- **Operational:** `_privaci` schema is created in the target database
  on first run. Customers must grant `CREATE SCHEMA` on the target. This
  is the only meaningful permission requirement beyond standard DML.
- **ADRs to be authored** as part of this change: license choice (ELv2),
  runtime (Python 3.12), state storage (in the target database), salt UX
  (user-supplied, no silent default), COPY-binary streaming, FK strategy
  (deferred constraints + topo sort), public/commercial split. (The billing-
  dimension ADR is commercial and lives in `privaci-commercial`; see §18.7.2.)
- **Tests:** 85% coverage minimum overall, 100% for `src/masking/`,
  `src/config/`, and `src/billing/` per `.cursorrules`. Integration
  tests use `pytest-postgresql` and a Docker Compose Postgres for
  ephemeral fixtures.
- **CI gates** (per `.cursorrules`): `black --check`, `isort --check`,
  `ruff check`, `mypy --strict`, `pytest --cov-fail-under=85`,
  `pip-audit`.
