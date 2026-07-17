# Post-GA engine OpenSpec roadmap

Engine-only priority queue after GA (2026-07). Cross-repo planning and plugin-layer
follow-ups live in the sibling commercial OpenSpec roadmap.

---

## Shipped (v1 baseline + v1.1)

| Change | Notes |
| --- | --- |
| [init-privaci-engine](changes/archive/2026-06-11-init-privaci-engine/) | Core pipeline, contracts, CLI |
| [add-keyed-pseudonymisation-v1_1](changes/archive/2026-07-07-add-keyed-pseudonymisation-v1_1/) | `hmac_hash`, `pseudonym` |
| [add-artifact-object-output](changes/archive/2026-07-07-add-artifact-object-output/) | `ObjectWriter` plugin |
| [add-config-scaffold-and-plan](changes/archive/2026-07-07-add-config-scaffold-and-plan/) | `init`, `plan` |
| [add-license-capabilities](changes/archive/2026-07-07-add-license-capabilities/) | Capability tokens |

---

## Priority queue (implementation order)

| # | Change | Phase / scope | Blocks |
| --- | --- | --- | --- |
| **1** | [add-schema-replication-modes](changes/add-schema-replication-modes/) | **Phase 1** — `assume_existing`, idempotent DDL | DBA-managed staging workflow |
| **2** | [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Dialect-neutral `_privaci` DDL + connection ABCs | All connectors |
| **3** | [add-schema-replication-modes](changes/add-schema-replication-modes/) | **Phases 2–3** — functions/views, matviews | Phase 1 |
| **4** | `catalog import-db-comments` | Public half of plugin `add-pii-annotation-catalog` | Plugin PII catalog |
| **5** | [add-conditional-masking-cel](changes/add-conditional-masking-cel/) | Optional `when:` CEL on column rules | — |
| **6** | [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) → [add-s3-object-connectors](changes/add-s3-object-connectors/) | Parquet/JSONL + S3 lake export | — |
| **7** | [add-mysql-source-target](changes/add-mysql-source-target/) → [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Same-engine connectors | **#2** |
| **8** | Cross-engine deterministic consistency *(proposed)* | Keyed identity stable across engines | **#7** |

**#1 and #2** may start in parallel. **#3** waits on Phase 1. **#7+** waits on **#2**.

Plugin-package follow-up for schema modes: report collectors only
(`add-schema-replication-report-evidence`) — no engine logic.

---

## OpenSpec index (all active changes)

| Change | Status |
| --- | --- |
| [add-schema-replication-modes](changes/add-schema-replication-modes/) | Proposed — prioritize Phase 1 |
| [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Proposed — critical path |
| [add-mysql-source-target](changes/add-mysql-source-target/) | Proposed — blocked on state abstraction |
| [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Proposed — blocked on MySQL |
| [add-conditional-masking-cel](changes/add-conditional-masking-cel/) | Proposed |
| [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) | Proposed |
| [add-s3-object-connectors](changes/add-s3-object-connectors/) | Proposed |

Legacy phase labels (A/B/C/D from 2026-06) are superseded by the numbered queue
above.
