## ADDED Requirements

### Requirement: Object URI parsing

The system SHALL parse object destination strings supporting bare filesystem
paths, `file://`, `s3://bucket/key`, and `azure-blob://account/container/blob`
(parse-only until a backend exists). Malformed URIs SHALL raise `StorageError`
with redacted messages.

#### Scenario: Local bare path

- **WHEN** the destination is `./reports/out.json`
- **THEN** the parser SHALL classify it as a local file path.

#### Scenario: S3 URI

- **WHEN** the destination is `s3://evidence/privaci/run-1/report.json`
- **THEN** the parser SHALL extract bucket and key components.

#### Scenario: Unknown scheme

- **WHEN** the destination is `ftp://host/path`
- **THEN** the engine SHALL exit `1` or `3` naming the unsupported scheme.

### Requirement: ObjectWriter plugin dispatch

The system SHALL expose `write_object(uri, data: bytes)` that delegates to
`ObjectWriter.write` from `load_plugins()`. Community mode SHALL write local
paths only. Cloud schemes without a registered plugin SHALL exit `3` with
remediation to install commercial or register `object_writer`.

#### Scenario: Community local write

- **WHEN** community mode writes to `/tmp/report.json`
- **THEN** the file SHALL contain the supplied bytes.

#### Scenario: Community cloud URI rejected

- **WHEN** community mode writes to `s3://bucket/key`
- **THEN** the engine SHALL exit `3` with plugin remediation.

#### Scenario: Commercial S3 write

- **WHEN** commercial is installed and credentials allow `PutObject`
- **THEN** `write_object("s3://bucket/key", data)` SHALL upload the object.

### Requirement: URI redaction in observability

Failed writes SHALL log and report errors using redacted URIs
(`s3://<redacted>`), never object payloads or credentials.

#### Scenario: S3 failure redaction

- **WHEN** an S3 write fails
- **THEN** structured logs SHALL not include the full object key path.
