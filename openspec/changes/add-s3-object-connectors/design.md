## Context

Export sinks (prior change) define local file writers. S3 is the production
destination for Business tier lake-house integrations. One connector abstraction
covers read and write against object storage.

## Goals / Non-Goals

**Goals:**

- Read objects from `s3://` URIs into the streaming batch interface.
- Write masked exports to `s3://` prefixes via multipart upload.
- Default to IAM role credentials on AWS; explicit keys via secrets URIs for
  dev/MinIO.
- Constant-memory streaming reads (range GET or line iterator for CSV/JSONL).

**Non-Goals:**

- Azure Blob / GCS (future connector plugins).
- S3 Select or Athena SQL sources.
- Writing unmasked objects.
- Cross-account bucket policy automation.

## Decisions

### D1. boto3 for S3 I/O

**Decision:** Use existing `boto3` client with configurable endpoint URL for
S3-compatible stores.

### D2. `ObjectStoreConnector` ABC

**Decision:** Methods `open_reader(uri) -> AsyncIterator[batch]`,
`open_writer(uri) -> RowSink`. S3 implementation registered as
`connector.s3` entry point.

### D3. CSV read defaults

**Decision:** Header row required by default; `delimiter`, `quote`, `encoding`
configurable. Sniff disabled for security (no ambiguous parsing).

### D4. Write layout

**Decision:** One object per table:
`s3://bucket/prefix/<schema>.<table>.<format>`. Partition children use child
table name.

### D5. Credentials

**Decision:** Credential chain: IAM role → `AWS_ACCESS_KEY_ID` env →
`config.aws_credentials` secret URI. Session tokens supported via URI query
params. Never log access keys.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Partial upload on crash | Multipart abort in `finally`; resume rewrites object (document) |
| Large CSV memory | Line-buffered read; never load whole object |
| MinIO parity | Contributor integration test behind marker |

## Open Questions

- Server-side encryption defaults (`AES256` vs `aws:kms`)? — document
  customer-owned bucket policy; engine honors bucket default.
