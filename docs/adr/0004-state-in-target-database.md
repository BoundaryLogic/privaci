# ADR-0004: Store run state in a `_privaci` schema in the target database

## Status

Accepted — 2026-05-28

## Context

PrivaCI needs persistent state for:

1. **Resumability** — a crashed 4-hour job should resume, not restart.
2. **Audit log** — a record of which columns were masked with which
   action, plus auto-detect findings and warnings, queryable for years.
3. **Source-DB identity** — a stable `source_db_hash` per source, used
   for run identity and resumability (any commercial billing use is out
   of scope for the engine; see ADR-0003).
4. **Drift detection (commercial v1.x)** — comparing the current
   catalog snapshot to the last one.
5. **Compliance reports (commercial v1.x)** — generated from audit-log
   history.

Where should this state live?

Alternatives considered:

- **S3 / blob storage** — external dependency, breaks air-gapped
  customers, adds another credential to manage.
- **Redis / managed KV** — extra moving part for a batch job.
- **Container-local SQLite** — state dies with the container; useless
  for CI/CD where every run starts in a fresh container.
- **Source database** — read-only by product policy.
- **Customer-managed metadata DB (separate connection string)** —
  configurable but onboarding friction; an additional secret to
  manage and an additional permission grant to request.

## Decision

State lives in the **target database**, in a dedicated `_privaci`
schema created idempotently on first run. Tables:

- `_privaci.runs` — one row per run.
- `_privaci.table_checkpoints` — one row per (run, table) for
  per-batch resumability.
- `_privaci.audit_log` — one row per masking event.

Customers grant `CREATE SCHEMA` and DML on `_privaci.*` to the
masking role. This is the only meaningful permission requirement
beyond standard DML on the masked tables.

## Consequences

### Why this is a strong choice

- **One unified location** for resumability, audit, drift, and reports.
- **No external dependencies** — PrivaCI stays a single container
  with two DB connections and nothing else.
- **Co-locates audit data with the masked data it describes.**
  Customer auditors query one database with the SQL skills they
  already have.
- **Survives container restarts** — central to the resumability
  promise.
- **Air-gap friendly** — works in environments with no internet egress.

### Trade-offs accepted

- **Customer must grant `CREATE SCHEMA`.** Documented in quickstart.
  Pre-flight check fails with a clear error if the grant is missing.
- **State and masked data share a database.** A catastrophic target
  failure loses both. Acceptable because target databases are by
  definition staging/dev, and the source remains untouched.
- **Schema version drift** — engine v2 reading `_privaci` schema
  written by v1 must apply additive migrations. The state-management
  module owns this.

### Forbidden patterns

- The `_privaci` schema is not for customer use. Application code
  must not read from or write to it. The pre-flight target-empty check
  excludes `_privaci` to avoid false positives on subsequent runs.
- We never write **input** PII to any `_privaci` table. Audit entries
  reference columns by name and counts, not values. The salt is stored
  as a 16-byte fingerprint, never as the salt itself.
