## 1. Config

- [ ] 1.1 Add top-level `sink` block: `type: file`, `format: parquet|jsonl`, `path`
- [ ] 1.2 Add optional `state_target` for sink-only runs; validate DSN at pre-flight
- [ ] 1.3 Wire Business+ tier gate for any file sink configuration

## 2. Sink implementations

- [ ] 2.1 Define `RowSink` ABC and batch interface
- [ ] 2.2 Implement JSONL sink (UTF-8, newline-delimited, stable key order)
- [ ] 2.3 Implement Parquet sink with pyarrow (schema from catalog, row groups = batch)
- [ ] 2.4 Type coercion map from Postgres OID → Parquet logical types

## 3. Runner integration

- [ ] 3.1 Dispatch target leg to `RowSink` when `sink` configured
- [ ] 3.2 Support dual-write (DB + file) behind Business tier check
- [ ] 3.3 Checkpoint/audit unchanged; record sink metadata in run summary

## 4. Tests & docs

- [ ] 4.1 Integration test: masked JSONL export, assert no source PII substrings
- [ ] 4.2 Integration test: Parquet round-trip read with pyarrow
- [ ] 4.3 Pre-flight disk space check for local paths
- [ ] 4.4 Update `docs/configuration.md`, `.env.example`, `CHANGELOG.md`
