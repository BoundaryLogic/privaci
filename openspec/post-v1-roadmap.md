# Post-v1.0 engine OpenSpec roadmap

OpenSpec changes for the public ELv2 engine after v1.0.0. Decisions locked
2026-06-19.

| Change | Phase | Notes |
| --- | --- | --- |
| [add-keyed-pseudonymisation-v1_1](changes/add-keyed-pseudonymisation-v1_1/) | A / 1.0.2 | `hmac_hash` and `pseudonym` masking actions |
| [add-conditional-masking-cel](changes/add-conditional-masking-cel/) | B | Optional `when:` CEL guard on column rules |
| [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) | C | Parquet and JSONL file sinks |
| [add-s3-object-connectors](changes/add-s3-object-connectors/) | C | S3 read/write for exports and object inputs |
| [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | D | Prerequisite for multi-database connectors |
| [add-artifact-object-output](changes/add-artifact-object-output/) | 1.0.2 | `ObjectWriter` plugin + artifact URI dispatch |

Implementation order: Phase A → B → C; `add-state-schema-abstraction` before
multi-database connector work.
