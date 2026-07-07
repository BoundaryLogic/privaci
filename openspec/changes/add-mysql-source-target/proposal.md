## Why

Customers standardize on MySQL and MariaDB (RDS Aurora MySQL, PlanetScale, on-prem)
alongside PostgreSQL. The engine is PostgreSQL-only today. Same-engine MySQL→MySQL
masking belongs in the public OSS engine — dialect connectors are core platform
capability, not proprietary overlay code.

## What Changes

- **Prerequisite:** `add-state-schema-abstraction` — dialect-neutral `_privaci` state
  and `CatalogBackend` / `StateBackend` contracts.
- **MySQL connector** in `src/privaci/connectors/mysql/`: `aiomysql` async driver,
  `mysql://` / `mariadb://` DSN schemes, catalog introspection, streaming,
  target DDL replication.
- **Capability gate:** `mysql_connector` token on `LicenseStatus.capabilities` (granted
  by the installed plugin contract); community mode without the token → exit **5**.
- Operator docs: supported versions, JSON/subsetting gaps, example DSNs.
- **Non-goals:** cross-engine PG→MySQL; FK-aware subsetting on MySQL v1.

## Capabilities

### New Capabilities

- `mysql-connector`: same-engine MySQL/MariaDB source and target support.

### Modified Capabilities

- `commercial-tier-contract`: document `mysql_connector` capability token.
- `engine-cli`: DSN scheme routing for `mysql` / `mariadb`.
- `state-and-audit`: consumed via `StateBackend` dialect implementation.

## Impact

- **Public repo only** for connector implementation.
- **Commercial repo:** grant `mysql_connector` capability from compliance-tier
  entitlement; no connector code in `privaci_commercial`.
- **Dependencies:** `add-state-schema-abstraction` must merge first.

## Non-goals

- PostgreSQL→MySQL cross-engine runs.
- FK-aware subsetting on MySQL (follow-up).
- `json_mask` path rules on MySQL JSON columns v1.
