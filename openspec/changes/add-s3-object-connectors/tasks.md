## 1. Connector abstraction

- [ ] 1.1 Define `ObjectStoreConnector` ABC (read iterator, write sink factory)
- [ ] 1.2 Register `connector.s3` entry point
- [ ] 1.3 Implement boto3 client factory with endpoint URL override

## 2. S3 read path

- [ ] 2.1 Parse `source: s3` config block (uri, format, csv options)
- [ ] 2.2 Implement CSV line reader → row dict batches
- [ ] 2.3 Implement JSONL and Parquet readers delegating to pyarrow where needed
- [ ] 2.4 Wire catalog-less mode: infer columns from first batch + config overrides

## 3. S3 write path

- [ ] 3.1 Resolve `sink.path` s3:// URIs in file sink module
- [ ] 3.2 Multipart upload wrapper for Parquet/JSONL streams
- [ ] 3.3 Abort multipart uploads on failure; audit partial state

## 4. Secrets & tier gates

- [ ] 4.1 Extend secrets resolver docs for AWS key URIs used by S3 connector
- [ ] 4.2 Business+ tier validation for any s3:// source or sink
- [ ] 4.3 moto unit tests; optional MinIO integration test

## 5. Docs

- [ ] 5.1 IAM policy example (read source bucket, write dest prefix)
- [ ] 5.2 Update `docs/configuration.md`, `CHANGELOG.md`
