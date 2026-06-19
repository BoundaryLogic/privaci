## Why

Business customers ingest CSV dumps and custom object exports from S3 into
the masking pipeline, and write masked Parquet/JSONL back to S3 for lake
house workflows. Reusing the file sink encoder from the export change avoids
a second implementation path.

## What Changes

- **S3 read connector** — `source: s3` with `uri`, optional `format: csv |
  jsonl | parquet`, compression, and column mapping for headerless CSV.
- **S3 write connector** — `sink.path: s3://bucket/prefix/...` using the same
  `RowSink` encoders; multipart upload for large outputs.
- **Credentials via secrets resolver** — `aws-sm://`, IAM role (default on
  Marketplace image), optional `env://` keys; no hardcoded keys.
- **Same connector layer** — shared `ObjectStoreConnector` used by read path
  and export sinks.
- **Tier gating:** Business+ for any S3 source or sink URI.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `streaming-pipeline`: S3 object read path feeding the masker; S3 write path
  for file sinks.
- `secrets-resolver`: Optional static credentials and session token URIs for
  S3-compatible endpoints (MinIO dev).

## Impact

- **Code:** `src/privaci/connectors/s3.py`, runner source dispatch, sink URI
  resolution.
- **Dependencies:** `boto3` (already present for secrets); optional `s3fs` not
  required if boto3 streaming suffices.
- **Docs:** IAM policy examples, MinIO compose recipe for contributors.
- **Tests:** moto-backed unit tests; integration marked `@pytest.mark.integration`.
