## ADDED Requirements

### Requirement: S3 object source (Business+ tier)

The streaming pipeline SHALL support reading source rows from an S3 object
URI when `source.type: s3` is configured. Supported formats SHALL include
`csv`, `jsonl`, and `parquet`. Rows SHALL be fed through the same masking
pipeline as database sources.

S3 source configuration SHALL require Business or Enterprise tier.

#### Scenario: CSV object masked export to DB target

- **WHEN** `source: { type: s3, uri: s3://bucket/in/users.csv, format: csv }`
  and a relational target is configured
- **THEN** masked rows SHALL land in the target table and the object SHALL
  never be written unmasked to any other location.

#### Scenario: Streaming read memory bound

- **WHEN** reading a multi-GB CSV object
- **THEN** the connector SHALL not download the entire object into memory
  before batching.

#### Scenario: Starter tier rejected

- **WHEN** the license tier is `starter` and `source.type: s3` is set
- **THEN** the engine SHALL exit `5` at config validation.

### Requirement: S3 object sink for exports

When `sink.path` uses an `s3://` URI, the file sink encoders SHALL upload
masked output via multipart upload. One object SHALL be written per streamed
table using the pattern `<prefix>/<schema>.<table>.<ext>`.

#### Scenario: Parquet upload to S3

- **WHEN** `sink: { type: file, format: parquet, path: s3://out/masked/ }`
  completes for table `public.users`
- **THEN** object `s3://out/masked/public.users.parquet` SHALL exist and
  SHALL contain only masked values.

#### Scenario: Failed run aborts multipart upload

- **WHEN** a run fails mid-upload
- **THEN** the connector SHALL abort in-flight multipart uploads and SHALL
  NOT leave a completed object with partial data.

### Requirement: Shared connector layer with file sinks

S3 read and write SHALL use the same `ObjectStoreConnector` abstraction
registered for the export-sinks feature. Parquet and JSONL encoding SHALL
reuse `RowSink` implementations without duplication.

#### Scenario: Connector reuse

- **WHEN** both local file and S3 sinks are tested with the same table batch
- **THEN** encoded bytes for JSONL and Parquet SHALL be identical aside from
  transport framing.
