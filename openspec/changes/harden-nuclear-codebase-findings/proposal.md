## Why

A full-tree nuclear codebase audit of `src/privaci/` found operator-visible
correctness bugs (CHECK DDL, exclude/orphan FKs, resume into partial schema,
UsageMeter `run_id` mismatch, dead `--force-restart` remediations), structural
debt that will compound under schema-mode work, and contract drift (docs/OpenSpec
vs code for PII redaction, exit-5 metering, matview/audit catalogs). This change
tracks and remediates that backlog before more replication features land on a
faulty base.

## What Changes

- **Fix CHECK constraint replication** so introspected `pg_get_constraintdef`
  output is not double-wrapped; add live-PG coverage.
- **Implement exclude / `null_orphan_fks`** — skip FK DDL to excluded
  referents; null orphan FK columns on the batch path; force binary COPY
  ineligible (fail `require_binary`) when nulling applies.
- **Pair UsageMeter `register_run` / `final_meter` on one `run_id`**; resume
  does not double-register.
- **Gate resume** — exit **2** if schema snapshot absent; if present, re-run
  idempotent `replicate_schema` before stream.
- **Implement `privaci run --force-restart`** (truncate/drop_create only;
  reject with fail policy); align all remediations.
- **Contract/docs sync**: hashed PII redaction; exit-5 License Manager (not
  metering); matview “later phase” leftover; audit event catalog;
  `commercial_layer_present`; skipped_object `reason` SHALL; CLI help
  ADR-0007 wording; error-codes for new resume/force-restart failures.
- **Structural hardening (non-breaking refactors)**: canonical `table_strategy`
  / `excluded_table_ids`; deepen Run lifecycle seam; split catalog snapshot
  serialize vs state persist; move skip disposition out of catalog; dual
  audit+emit helper.
- **Medium correctness**: layer checkpoint durability; identifier safety for
  views/functions; composite UNIQUE masking; `drop_create` excludes `_privaci`;
  tighten observability free-text redaction allowlist.
- **Ops/pin notes**: document engine-pin lag for commercial; no silent claim
  that Unreleased schema modes ship in `v1.1.0` images.

No intentional **BREAKING** public CLI/config removals (`null_orphan_fks` kept).

## Capabilities

### New Capabilities

- `run-lifecycle`: Explicit open/stream/close run seam (schema prepare, meter
  pairing, finish/abort, audit+emit recording) so CLI/resume share one policy
  surface.

### Modified Capabilities

- `schema-replication`: CHECK DDL emission; exclude-FK / `null_orphan_fks`;
  `drop_create` must not wipe `_privaci`; view/function identifier gates for DDL.
- `state-and-audit`: Resume requires completed schema phase (or re-replicate);
  remediations match real CLI; audit event types documented consistently.
- `commercial-tier-contract`: UsageMeter start/end share `run_id`; resume
  register/final policy.
- `observability`: Redaction format is hashed length+digest (not 8-char
  preview); `commercial_layer_present` reflects plugin install; free-text field
  redaction defaults; document current `created_object` / `skipped_object`
  audit shapes (definition-only matview event types stay in sibling
  `add-schema-replication-modes`).
- `config-yaml`: Document and enforce the chosen exclude / `null_orphan_fks`
  contract (implement or reject the flag).
- `engine-cli`: `--force-restart` on `run` **or** remove references; ADR-0007
  help text for contract-version / commercial hints.
- `streaming-pipeline`: Checkpoint durability across non-cycle layer siblings
  (or documented cycle-only single transaction).
- `sql-identifier-safety`: Extend safe-identifier validation beyond tables to
  views, functions, and constraint/index/sequence names used in dynamic SQL.
- `masking-pipeline` / `deterministic-faker`: Composite UNIQUE uniqueness
  semantics (single-column only or joint seed).
- `postgres-catalog`: Introspected check-constraint shape matches emitters;
  snapshot persistence ownership clarified vs state.

## Impact

- **Code:** `schema/ddl.py`, `schema/replicate.py`, `schema/objects.py`,
  `pipeline/runner.py`, `pipeline/lifecycle.py`, `pipeline/streaming.py`,
  `state/resume.py`, `catalog/*`, `cli/*`, `observability/redact.py`,
  `mask/column_masker.py`, config models/docs.
- **Docs:** `configuration.md`, `observability.md`, `error-codes.md`,
  `state-schema.md`, CLI references, CHANGELOG.
- **Tests:** integration fixtures for CHECK + exclude-FK; unit tests for meter
  id pairing and resume schema gate.
- **Commercial:** no pin bump required for public fixes; pin bump remains a
  separate release step for schema-mode features already Unreleased.
- **OpenSpec:** sibling `add-schema-replication-modes` remains for unfinished
  Phase 4/report cells, matview definition-only / `definition_only_object`,
  and related report collectors; this change owns nuclear harden backlog.
