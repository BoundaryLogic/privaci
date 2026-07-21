# Post-GA engine OpenSpec roadmap

Engine-only priority queue after GA (2026-07). Cross-repo planning and plugin-layer
follow-ups live in the sibling commercial OpenSpec roadmap.

---

## Shipped (v1 baseline + v1.1 + schema modes + DDL phases + v1.3)

| Change | Notes |
| --- | --- |
| [init-privaci-engine](changes/archive/2026-06-11-init-privaci-engine/) | Core pipeline, contracts, CLI |
| [add-keyed-pseudonymisation-v1_1](changes/archive/2026-07-07-add-keyed-pseudonymisation-v1_1/) | `hmac_hash`, `pseudonym` |
| [add-artifact-object-output](changes/archive/2026-07-07-add-artifact-object-output/) | `ObjectWriter` plugin |
| [add-config-scaffold-and-plan](changes/archive/2026-07-07-add-config-scaffold-and-plan/) | `init`, `plan` |
| [add-license-capabilities](changes/archive/2026-07-07-add-license-capabilities/) | Capability tokens |
| [add-schema-replication-modes](changes/archive/2026-07-17-add-schema-replication-modes/) | `assume_existing`, views/functions/matviews, elevated objects |
| [add-pg-dump-style-ddl-phases](changes/archive/2026-07-20-add-pg-dump-style-ddl-phases/) | pre-data / data / post-data; secondary indexes + triggers post-load |
| [harden-nuclear-codebase-findings](changes/archive/2026-07-20-harden-nuclear-codebase-findings/) | Schema/resume/observability hardening |
| [add-conditional-masking-cel](changes/archive/2026-07-21-add-conditional-masking-cel/) | Optional `when:` CEL (`conditional_masking`) |
| [add-pii-catalog-import](changes/archive/2026-07-21-add-pii-catalog-import/) | `catalog import-db-comments` + sidecar schema |

---

## Priority queue (implementation order)

| # | Change | Phase / scope | Blocks |
| --- | --- | --- | --- |
| **1** | [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Dialect-neutral `_privaci` DDL + connection ABCs | All connectors |
| **2** | [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) → [add-s3-object-connectors](changes/add-s3-object-connectors/) | Parquet/JSONL + S3 lake export | — |
| **3** | [add-mysql-source-target](changes/add-mysql-source-target/) → [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Same-engine connectors | **#1** |
| **4** | Cross-engine deterministic consistency *(proposed)* | Keyed identity stable across engines | **#3** |

**v1.3.0 public batch (this release):** CEL `when:` + PII catalog import + DDL
phases (already on `main`).

Plugin-package follow-ups (commercial, later): report `ddl_phase` evidence, PII
catalog validate/drift, tenant GTM.

---

## OpenSpec index (all active changes)

| Change | Status |
| --- | --- |
| [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Proposed — critical path for connectors |
| [add-mysql-source-target](changes/add-mysql-source-target/) | Proposed — blocked on state abstraction |
| [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Proposed — blocked on MySQL |
| [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) | Proposed |
| [add-s3-object-connectors](changes/add-s3-object-connectors/) | Proposed |

Legacy phase labels (A/B/C/D from 2026-06) are superseded by the numbered queue
above.
