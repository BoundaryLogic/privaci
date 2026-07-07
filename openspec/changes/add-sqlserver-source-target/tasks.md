# Tasks: add-sqlserver-source-target

> **Blocked by:** `add-state-schema-abstraction`, `add-mysql-source-target`.

## 0. Prerequisites

- [ ] 0.1 `add-mysql-source-target` merged (connector framework stable)
- [ ] 0.2 `add-state-schema-abstraction` pinned

## 1. Connector implementation

- [ ] 1.1 Pin `aioodbc` in requirements; document ODBC Driver 18 prerequisite
- [ ] 1.2 `src/privaci/connectors/sqlserver/` — DSN parse (`mssql://`, `sqlserver://`)
- [ ] 1.3 Catalog introspection (`sys.tables`, FK metadata)
- [ ] 1.4 Streaming read/write with keyset pagination
- [ ] 1.5 Target DDL replication and `_privaci` state via `StateBackend`

## 2. Authentication

- [ ] 2.1 SQL login via DSN/secrets (`sqlserver_connector` capability)
- [ ] 2.2 Entra ID token auth in `auth.py` (`sqlserver_entra_auth` capability)
- [ ] 2.3 Tier gate via capability tokens only — no tier-name strings in engine

## 3. Preflight & enforcement

- [ ] 3.1 Privilege checks (`SELECT`, `CREATE TABLE`, `INSERT`)
- [ ] 3.2 Cross-engine rejection → exit **2**

## 4. Tests & docs

- [ ] 4.1 Unit tests with mocked catalog
- [ ] 4.2 Integration test (SQL login) — `@pytest.mark.integration`, nightly/manual initially
- [ ] 4.3 `docs/sqlserver-connector.md`; link from `docs/README.md`
- [ ] 4.4 `CHANGELOG.md` [Unreleased]

## 5. Plugin follow-up (separate PR in plugin package)

- [ ] 5.1 Grant `sqlserver_connector` / `sqlserver_entra_auth` capabilities
- [ ] 5.2 Add ODBC Driver 18 + unixODBC to commercial Dockerfile
- [ ] 5.3 Bump `.engine-pin`
