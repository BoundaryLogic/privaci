# Post-GA engine OpenSpec roadmap

Engine-only priority queue. Cross-repo tier planning and plugin-package
follow-ups live in the sibling private OpenSpec roadmap and its ADR-0013
(capability placement principle).

Distribution / listing go-live is complete — do not treat historical listing
checklist tasks as blockers for engine work.

---

## Shipped (v1 baseline through v1.3+)

| Change | Notes |
| --- | --- |
| [init-privaci-engine](changes/archive/2026-06-11-init-privaci-engine/) | Core pipeline, contracts, CLI |
| [add-keyed-pseudonymisation-v1_1](changes/archive/2026-07-07-add-keyed-pseudonymisation-v1_1/) | `hmac_hash`, `pseudonym` |
| [add-artifact-object-output](changes/archive/2026-07-07-add-artifact-object-output/) | `ObjectWriter` plugin |
| [add-config-scaffold-and-plan](changes/archive/2026-07-07-add-config-scaffold-and-plan/) | `init`, `plan` |
| [add-license-capabilities](changes/archive/2026-07-07-add-license-capabilities/) | Capability tokens |
| [add-schema-replication-modes](changes/archive/2026-07-17-add-schema-replication-modes/) | `assume_existing`, views/functions/matviews |
| [add-pg-dump-style-ddl-phases](changes/archive/2026-07-20-add-pg-dump-style-ddl-phases/) | pre-data / data / post-data |
| [harden-nuclear-codebase-findings](changes/archive/2026-07-20-harden-nuclear-codebase-findings/) | Schema/resume/observability hardening |
| [add-conditional-masking-cel](changes/archive/2026-07-21-add-conditional-masking-cel/) | Optional `when:` CEL |
| [add-pii-catalog-import](changes/archive/2026-07-21-add-pii-catalog-import/) | `catalog import-db-comments` |
| [harden-ner-mask-require-spacy](changes/archive/2026-07-21-harden-ner-mask-require-spacy/) | NER fail-closed |

---

## Priority queue (implementation order)

Aligned with the placement principle (community = workflow-complete on
well-formed schemas; plugin-installed = fidelity + proof).

| # | Item | Scope | Notes |
| --- | --- | --- | --- |
| **P1** | **Public subsetting (Snaplet floor)** | `percent` / `rowLimit` / `where` + declared-FK closure + optional declared virtual edges | Relocate declared-FK closure into the public engine. Define `percent` as **root sampling pre-closure**; document expansion factor. Ships with the private ADR-0013 token redraw. |
| **P1b** | **Intra-row composition** | `copy` (+ transforms such as `upper`/`lower`/`trim`), `concat` / format over **masked** sibling columns; topological mask order; fail closed on cycles / missing `from` | **Free.** Customer ask (e.g. `normalized_email` from masked `email`; composed locals). Prefer explicit `copy`/`concat` over opaque “persona” first; optional shared persona seed later. OpenSpec + nuclear-openspec before implement. |
| **P2** | **Value-based PII scanning + coverage report** | Sample N rows; Luhn/SSN/IBAN/phone/email/entropy; masked / passthrough / unreviewed | CI fail flag stays plugin-installed. |
| **P3** | **Published benchmark** | `make bench` vs `pg_dump` / Greenmask at 10 GB and 100 GB | Pulled forward; honest single-stream numbers OK. Parallelism is separate (P5). |
| **P4** | **Platform bet = export sinks** | Masked Parquet/CSV (then object storage) | Prefer over MySQL first — reuses masking core; MySQL forks catalog/FK/COPY. Sort community vs plugin via ADR-0013 at build time (lean: community if quickstart-complete). |
| **P5** | **Table-parallel streaming** | Independent tables within a topo layer | Only if P3 shows need; cyclic SCCs need per-worker connections. |
| **P6** | **Incremental refresh** | Watermark-based delta (v2) | Named v2; forward-capture watermark columns in v1 state (private C-G4). Placement named-exception decision due at start. |
| **P7** | **Fleet (thin)** | Docs now: same-salt cross-DB consistency (+ keyed safer path); `fleet.yaml` later | Cross-DB implied edges deferred. |

### General attach-points (not separate milestones)

| Item | Notes |
| --- | --- |
| Delete `conditional_masking` capability gate | CEL `when:` is community; gate removal is next public release (private C-G1). |
| Capture nullable `updated_at` / LSN watermarks in `_privaci` | When available on source; prep for P6 without a later migration. |
| `ai_refine` | Action exists in config schema; **not implemented**. Docs must not claim live Bedrock/Azure calls. Community mode rejects; plugin stubs must fail closed until built. |

---

## OpenSpec index (active changes)

| Change | Status vs this roadmap |
| --- | --- |
| [add-state-schema-abstraction](changes/add-state-schema-abstraction/) | Still required before MySQL/SQL Server; **deprioritized** vs P1–P3 (export sinks P4 may proceed without it). |
| [add-export-sinks-parquet-jsonl](changes/add-export-sinks-parquet-jsonl/) | Becomes **P4** |
| [add-s3-object-connectors](changes/add-s3-object-connectors/) | Follows P4 |
| [add-mysql-source-target](changes/add-mysql-source-target/) | Parked behind P1–P4; blocked on state abstraction |
| [add-sqlserver-source-target](changes/add-sqlserver-source-target/) | Parked behind MySQL |

Public subsetting (P1), intra-row composition (P1b), and value scanning (P2)
need new OpenSpecs before implementation (nuclear-openspec gate).

---

## Explicit deferrals

| Item | Until |
| --- | --- |
| MySQL / SQL Server connectors | After P1 wedge + P4 bet; state abstraction first |
| Cross-engine deterministic consistency | Not planned (same-engine only) |
| Incremental refresh product | P6 / v2 |
| Table-parallel workers | P5 if bench demands |
| Advertising `ai_refine` | Implementation + fail-closed connectors |
