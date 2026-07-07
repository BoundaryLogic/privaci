# Tasks: add-mysql-source-target

> **Blocked by:** `add-state-schema-abstraction`. Commercial repo only grants
> `mysql_connector` capability — no connector code there.

## 0. Prerequisite

- [ ] 0.1 Merge `add-state-schema-abstraction`
- [ ] 0.2 Verify `_privaci` DDL applies on MySQL via `StateBackend`

## 1. Connector scaffold

- [ ] 1.1 Pin `aiomysql` in `requirements.in` / `requirements.txt`
- [ ] 1.2 `src/privaci/connectors/mysql/` — pool, DSN parse (`mysql://`, `mariadb://`)
- [ ] 1.3 Register `CatalogBackend` + connection factory for MySQL DSN schemes
- [ ] 1.4 Add `mysql_connector` to capability contract docs

## 2. Catalog

- [ ] 2.1 Introspect tables/columns/PK/FK from `information_schema`
- [ ] 2.2 Map to pipeline catalog models
- [ ] 2.3 Unit tests with mocked catalog rows

## 3. Streaming & DDL

- [ ] 3.1 Keyset pagination reader on PK columns
- [ ] 3.2 Parameterized batch INSERT writer
- [ ] 3.3 Target schema replication (`schema_mode` / `on_existing_data` parity)
- [ ] 3.4 Integrate masking pipeline (reuse transform dispatch)

## 4. Preflight & capability gate

- [ ] 4.1 MySQL privilege checks (`SELECT`, `CREATE`, `INSERT`)
- [ ] 4.2 Gate on `mysql_connector` capability → exit **5**
- [ ] 4.3 Reject `json_mask` on MySQL JSON columns → exit **3**

## 5. Tests & docs

- [ ] 5.1 Integration: `tests/integration/test_mysql_roundtrip.py` (`@pytest.mark.integration`)
- [ ] 5.2 `docs/mysql-connector.md`; link from `docs/README.md`
- [ ] 5.3 `.env.example` example DSNs; `CHANGELOG.md` [Unreleased]

## 6. Plugin follow-up (separate PR in plugin package)

- [ ] 6.1 Grant `mysql_connector` in `capabilities_for_tier` (compliance tier)
- [ ] 6.2 Update licensing docs; bump `.engine-pin`
