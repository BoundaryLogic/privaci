# Post-GA engine OpenSpec roadmap

Engine-only priority queue after GA (2026-07). Cross-repo planning and plugin-layer
follow-ups live in the sibling commercial OpenSpec roadmap.

---

## Shipped (v1 baseline + v1.1 + schema modes)

| Change | Notes |
| --- | --- |
| [init-privaci-engine](changes/archive/2026-06-11-init-privaci-engine/) | Core pipeline, contracts, CLI |
| [add-keyed-pseudonymisation-v1_1](changes/archive/2026-07-07-add-keyed-pseudonymisation-v1_1/) | `hmac_hash`, `pseudonym` |
| [add-artifact-object-output](changes/archive/2026-07-07-add-artifact-object-output/) | `ObjectWriter` plugin |
| [add-config-scaffold-and-plan](changes/archive/2026-07-07-add-config-scaffold-and-plan/) | `init`, `plan` |
| [add-license-capabilities](changes/archive/2026-07-07-add-license-capabilities/) | Capability tokens |
| [add-schema-replication-modes](changes/archive/2026-07-17-add-schema-replication-modes/) | `assume_existing`, views/functions/matviews, elevated objects |

---

## Priority queue (implementation order)

| # | Change | Phase / scope | Blocks |
| --- | --- | --- | --- |
| **1** | [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Dialect-neutral `_privaci` DDL + connection ABCs | All connectors |
| **2** | [add-pg-dump-style-ddl-phases](changes/add-pg-dump-style-ddl-phases/) | pre-data / data / post-data; secondary indexes + triggers post-load | — |
| **3** | `catalog import-db-comments` | Public half of plugin `add-pii-annotation-catalog` | Plugin PII catalog |
| **4** | [add-conditional-masking-cel](changes/add-conditional-masking-cel/) | Optional `when:` CEL on column rules | — |
| **5** | [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) → [add-s3-object-connectors](changes/add-s3-object-connectors/) | Parquet/JSONL + S3 lake export | — |
| **6** | [add-mysql-source-target](changes/add-mysql-source-target/) → [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Same-engine connectors | **#1** |
| **7** | Cross-engine deterministic consistency *(proposed)* | Keyed identity stable across engines | **#6** |

Plugin-package follow-up for schema modes: report collectors only
(`add-schema-replication-report-evidence`) — no engine logic.

---

## OpenSpec index (all active changes)

| Change | Status |
| --- | --- |
| [add-pg-dump-style-ddl-phases](changes/add-pg-dump-style-ddl-phases/) | Implementing — nuclear Highs addressed |
| [harden-nuclear-codebase-findings](changes/harden-nuclear-codebase-findings/) | Implemented — archive pending |
| [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Proposed — critical path |
| [add-mysql-source-target](changes/add-mysql-source-target/) | Proposed — blocked on state abstraction |
| [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Proposed — blocked on MySQL |
| [add-conditional-masking-cel](changes/add-conditional-masking-cel/) | Proposed |
| [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) | Proposed |
| [add-s3-object-connectors](changes/add-s3-object-connectors/) | Proposed |

Legacy phase labels (A/B/C/D from 2026-06) are superseded by the numbered queue
above.
