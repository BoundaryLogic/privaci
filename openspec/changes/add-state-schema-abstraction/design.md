## Context

PostgreSQL-specific SQL is embedded in `privaci.state` and `privaci.catalog`.
MySQL/SQL Server work requires parallel implementations of the same logical
operations. A backend layer is the prerequisite tracked in post-MVP roadmap
(§27 init tasks).

## Goals / Non-Goals

**Goals:**

- Stable `StateBackend` and `CatalogBackend` ABCs in `privaci.contracts`.
- Default PostgreSQL backends preserve current behavior byte-for-byte on DDL
  semantics (jsonb → JSON, timestamptz → timestamptz, etc.).
- Pipeline, resume, and audit code depend on ABCs only.
- Idempotent schema creation expressed once as logical schema metadata.

**Non-Goals:**

- Shipping MySQL or SQL Server backends in this change (follow-on changes).
- Moving `_privaci` off the target database.
- Changing checkpoint or audit column semantics.
- SQL dialect auto-detection beyond connection URL scheme.

## Decisions

### D1. Two backends: state vs catalog

**Decision:** Separate ABCs. Catalog is read-heavy and source-scoped; state is
write-heavy and target-scoped. A single "DatabaseBackend" would force awkward
split connections.

### D2. Logical schema metadata

**Decision:** Define `_privaci` tables as dataclasses (`LogicalTable`,
`LogicalColumn`, `LogicalIndex`) with dialect emitters in each backend.

**Alternatives:** ORM (SQLAlchemy) — heavy dependency for three tables.
Raw SQL strings per backend — duplicate logic; metadata centralizes shape.

### D3. Postgres as default via entry point

**Decision:** `privaci.plugins` entry `state_backend.postgres` and
`catalog_backend.postgres` registered by the public engine. Future
`*.mysql` / `*.mssql` are optional plugins.

### D4. CONTRACT_VERSION minor bump

**Decision:** Additive ABCs bump minor (1.0 → 1.1). Commercial pin check
accepts same major. Document in OCI label and `privaci --contract-version`.

### D5. Migration path for existing `_privaci` schemas

**Decision:** Postgres backend detects existing tables; additive migrations
only. No automatic rewrite for other dialects until those backends ship.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Refactor regression on resume/checkpoints | Full existing integration suite on Postgres backend |
| Over-abstracted catalog API | Start with methods MVP uses; extend when MySQL spikes land |
| Plugin discovery ordering | Document single-backend-per-dialect; fail on duplicate registration |

## Open Questions

- Should `CatalogBackend` expose streaming hints (COPY vs batch)? — defer to
  streaming-pipeline change when MySQL streaming is designed.
