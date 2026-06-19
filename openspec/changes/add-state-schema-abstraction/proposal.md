## Why

Run state, checkpoints, and audit today live in `_privaci` via hand-written
PostgreSQL DDL and asyncpg queries. That coupling blocks MySQL and SQL Server
support: each engine needs different catalog queries, identifier quoting, and
DDL for the same logical tables (`runs`, `table_checkpoints`, `audit_log`).

Abstracting state and catalog behind stable backend contracts lets the public
engine add databases incrementally without rewriting the streaming pipeline,
resume gate, or audit writers.

## What Changes

- **`StateBackend` contract** — idempotent schema bootstrap, run lifecycle,
  checkpoint read/write, audit append. PostgreSQL implementation wraps existing
  SQL; future backends implement the same ABC.
- **`CatalogBackend` contract** — introspection for tables, columns, PKs, FKs,
  partitions. `PostgresCatalogBackend` moves current `privaci.catalog` logic
  behind the interface.
- **DDL abstraction** — `_privaci` schema definition expressed as backend-neutral
  metadata (table/column types as logical enums), emitted per dialect.
- **`CONTRACT_VERSION` minor bump** — additive ABCs; commercial layer must
  pin compatible engine; document in ADR and release notes.
- **No new tier gate** — infrastructure refactor; all tiers benefit when
  additional databases ship.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `state-and-audit`: State access routed through `StateBackend`; DDL no longer
  hard-coded only in Postgres modules.
- `commercial-tier-contract`: Adds `StateBackend` and `CatalogBackend` ABCs;
  entry-point discovery for optional dialect plugins.

## Impact

- **Code:** `src/privaci/state/` refactor, `src/privaci/catalog/` refactor,
  `src/privaci/contracts/`, `src/privaci/pipeline/runner.py` (inject backends).
- **Breaking:** None for operators on PostgreSQL-only deployments if default
  backend unchanged.
- **Contracts:** Minor `CONTRACT_VERSION` bump (e.g., `1.0` → `1.1`).
- **Docs:** ADR for backend abstraction; `docs/extending-privaci.md` (dialect
  plugins).
- **Tests:** Contract conformance tests; Postgres backend must pass existing
  integration suite unchanged.
