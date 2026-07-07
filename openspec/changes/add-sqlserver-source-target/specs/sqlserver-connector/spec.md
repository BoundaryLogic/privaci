# sqlserver-connector Specification

## Purpose

Same-engine Microsoft SQL Server source and target support in the public OSS engine.

## ADDED Requirements

### Requirement: SQL Server DSN schemes

The engine SHALL accept `mssql://` and `sqlserver://` DSNs and connect via `aioodbc`
with ODBC Driver 18 when `sqlserver_connector` is granted.

#### Scenario: Same-engine SQL Server run

- **WHEN** source and target DSNs both use `mssql://`, `sqlserver_connector` is
  granted, and SQL authentication credentials are valid
- **THEN** `privaci run` SHALL complete with audit state in `_privaci`.

#### Scenario: Cross-engine rejected

- **WHEN** source is PostgreSQL and target is SQL Server
- **THEN** preflight SHALL exit **2** with unsupported cross-engine message.

#### Scenario: Capability absent

- **WHEN** DSN uses `mssql://` and `sqlserver_connector` is not granted
- **THEN** exit **5** before connection.

### Requirement: Catalog from system views

The SQL Server connector SHALL introspect user tables via `INFORMATION_SCHEMA` and
`sys` catalog views and produce FK-aware metadata for load ordering.

#### Scenario: Identity column pagination

- **WHEN** a table has an `IDENTITY` primary key
- **THEN** streaming SHALL use keyset pagination without skipping or duplicating rows.

### Requirement: Entra ID auth capability

Entra ID token and managed-identity authentication SHALL require the
`sqlserver_entra_auth` capability in addition to `sqlserver_connector`.

#### Scenario: Entra auth without capability

- **WHEN** auth mode is `entra_token` and `sqlserver_entra_auth` is not granted
- **THEN** exit **5** with remediation before connection.

#### Scenario: Entra auth with capability

- **WHEN** `sqlserver_entra_auth` is granted and a valid access token is supplied
- **THEN** the connector SHALL connect without SQL password in DSN.

### Requirement: Parameterized SQL only

Value payloads SHALL use parameterized queries. Identifiers SHALL be bracket-quoted per
T-SQL rules.

#### Scenario: Reserved word table name

- **WHEN** catalog returns table `[user]`
- **THEN** generated SQL SHALL bracket-quote identifiers and SHALL NOT concatenate cell
  values into SQL text.

### Requirement: ODBC runtime documented

Operator documentation SHALL state that SQL Server requires ODBC Driver 18 and how the
Official container image satisfies that requirement.

#### Scenario: Self-built container

- **WHEN** an operator builds a custom image from the OSS Dockerfile only
- **THEN** `docs/sqlserver-connector.md` SHALL document installing ODBC Driver 18.
