## Why

Enterprise accounts run Microsoft SQL Server (RDS SQL Server, Azure SQL, on-prem) and
need the same in-VPC masking workflow as PostgreSQL and MySQL. Same-engine SQL Server
connectors belong in the public OSS engine, reusing the MySQL connector framework and
state schema abstraction.

## What Changes

- **Prerequisites:** `add-state-schema-abstraction`, `add-mysql-source-target`.
- **SQL Server connector** in `src/privaci/connectors/sqlserver/`: `aioodbc` + ODBC
  Driver 18, `mssql://` / `sqlserver://` DSN schemes.
- **Capability gates:** `sqlserver_connector` (base); `sqlserver_entra_auth` for Entra
  ID / managed-identity paths (granted by plugin contract).
- Container image note: ODBC runtime ships in the **official container image** only;
  OSS engine documents driver requirement for self-built images.
- **Non-goals:** cross-engine; FK subsetting; bcp bulk copy v1.

## Capabilities

### New Capabilities

- `sqlserver-connector`: same-engine SQL Server source and target support.

### Modified Capabilities

- `commercial-tier-contract`: `sqlserver_connector`, `sqlserver_entra_auth` tokens.

## Impact

- **Public repo:** connector implementation.
- **Commercial repo:** capability grants + Dockerfile ODBC layer (no connector logic).
- **Dependencies:** MySQL connector framework + state abstraction.

## Non-goals

- Cross-engine PG/MySQL→SQL Server.
- FK-aware subsetting on SQL Server v1.
- `bcp` / bulk copy fast path (security review required).
