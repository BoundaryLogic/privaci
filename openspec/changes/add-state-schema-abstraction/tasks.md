## 1. Contracts

- [ ] 1.1 Define `StateBackend` ABC: `ensure_schema`, `start_run`, `finish_run`,
      `write_checkpoint`, `mark_table_done`, `append_audit`, `find_resumable_run`
- [ ] 1.2 Define `CatalogBackend` ABC: `discover`, `topo_sort`, cycle helpers
- [ ] 1.3 Define logical schema metadata types for `_privaci` tables
- [ ] 1.4 Bump `CONTRACT_VERSION` minor; update CI label check and docs
- [ ] 1.5 Register Postgres backends via `privaci.plugins` entry points

## 2. Postgres implementations

- [ ] 2.1 Implement `PostgresStateBackend` wrapping existing state SQL
- [ ] 2.2 Implement `PostgresCatalogBackend` delegating to current catalog module
- [ ] 2.3 Wire factory: select backend from DSN scheme (`postgresql://`)

## 3. Pipeline integration

- [ ] 3.1 Inject `StateBackend` + `CatalogBackend` into runner and pre-flight
- [ ] 3.2 Remove direct asyncpg state/catalog calls from pipeline hot path
- [ ] 3.3 Preserve all resume, checkpoint, and audit semantics (no behavior change)

## 4. Tests & docs

- [ ] 4.1 Contract conformance tests with in-memory fake backend
- [ ] 4.2 Run full existing state/resume integration suite on Postgres backend
- [ ] 4.3 Author ADR; update `docs/extending-privaci.md`, `CHANGELOG.md`
