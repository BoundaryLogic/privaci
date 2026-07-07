# mysql-connector Specification

## Purpose

Same-engine MySQL/MariaDB source and target support in the public OSS engine.

## ADDED Requirements

### Requirement: MySQL DSN schemes

The engine SHALL accept source and target URLs with scheme `mysql` or `mariadb` and
connect via async `aiomysql` when the `mysql_connector` capability is granted.

#### Scenario: Same-engine MySQL run

- **WHEN** source and target DSNs both use `mysql://` and
  `mysql_connector` is in `LicenseStatus.capabilities`
- **THEN** `privaci run` SHALL mask data with deterministic transforms and write
  audit state to target `_privaci`.

#### Scenario: Cross-engine rejected

- **WHEN** source is `postgresql://` and target is `mysql://`
- **THEN** preflight SHALL fail with exit **2** and an unsupported cross-engine message.

#### Scenario: Capability absent

- **WHEN** either DSN uses `mysql://` and `mysql_connector` is not granted
- **THEN** the command SHALL exit **5** before connecting.

### Requirement: Catalog introspection

The MySQL connector SHALL introspect user tables (excluding system schemas) and
produce catalog metadata compatible with the public pipeline, including primary keys
and foreign keys where declared in InnoDB.

#### Scenario: FK graph for load order

- **WHEN** source has InnoDB foreign keys among user tables
- **THEN** introspection SHALL populate FK edges for topological load ordering.

#### Scenario: MyISAM without FK metadata

- **WHEN** a table uses MyISAM without catalog FKs
- **THEN** introspection SHALL complete with a WARNING and treat tables as
  independent for ordering.

### Requirement: State schema on target

The connector SHALL apply dialect-specific `_privaci` DDL via `StateBackend` before the
first write.

#### Scenario: Resume on MySQL target

- **WHEN** a prior run left checkpoints in `_privaci.runs` on the MySQL target
- **THEN** `privaci resume` SHALL continue from checkpoint using the same semantics as
  PostgreSQL.

### Requirement: JSON and subsetting limitations

MySQL connector v1 SHALL NOT support `json_mask` path rules or FK-aware subsetting.

#### Scenario: json_mask on MySQL JSON column

- **WHEN** mask-rules references `json_mask` on a MySQL `JSON` column
- **THEN** config validation SHALL fail with exit **3** naming the dialect limitation.

### Requirement: Parameterized SQL only

All read and write queries SHALL use parameterized statements. Identifiers SHALL be
quoted via a MySQL identifier quoter.

#### Scenario: Reserved word table name

- **WHEN** streaming reads table `user`
- **THEN** generated SQL SHALL quote identifiers and SHALL NOT interpolate cell values
  into query text.
