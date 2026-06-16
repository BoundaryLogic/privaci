# Architecture overview

This page summarizes the MVP architecture documented in full in
`openspec/changes/init-privaci-engine/design.md` and the numbered ADRs under
[`adr/`](../adr/README.md).

## Product shape

PrivaCI is a **batch CLI**, not a daemon. A container (or local process) boots,
masks every configured table, writes an audit trail, and exits. Data never
leaves the customer's VPC; PII is processed in memory only.

| Goal | How |
|------|-----|
| Constant memory on 100 GB+ databases | COPY-binary streaming with fixed batch size (default 10k rows) |
| Referential integrity | Topological table order + deferred constraints for cycles |
| Crash recovery | Per-batch checkpoints in `_privaci.table_checkpoints` |
| Auditability | `_privaci.runs` + `_privaci.audit_log` on the target |
| Commercial extensibility | Stable ABCs in `privaci.contracts`, loaded via entry points |

## Runtime (D1)

**Python 3.12** with `asyncio`, `asyncpg`, `pydantic`, and `typer`. SpaCy
(`en_core_web_sm`) powers Level-2 NER when the `nlp` extra is installed. The
production image is `python:3.12-slim`, non-root (UID 10001).

Go and Rust were considered for throughput; Python wins because SpaCy has no
production-grade equivalent and the batch model tolerates a 1–2 s cold start.

## Streaming pipeline (D2)

```
source DB ──COPY TO STDOUT (binary)──► decode ──► mask ──► encode ──COPY FROM STDIN──► target DB
```

Both COPY legs run concurrently in one asyncio event loop. At most one batch
of rows resides in RAM. Unsupported binary types fall back to text-mode COPY.

Key modules: `privaci.stream`, `privaci.mask`, `privaci.pipeline`.

## Foreign keys (D3)

1. Build an FK graph from `information_schema` / `pg_catalog`.
2. Topologically sort tables; load parents before children.
3. Break cycles by deferring the lowest-cost edge (`SET CONSTRAINTS ALL DEFERRED`).
4. Warn on polymorphic / soft FK patterns that catalogs cannot see.

## State & resumability (D4, D5)

All run state lives in a **`_privaci` schema on the target database**:

| Table | Purpose |
|-------|---------|
| `runs` | Run metadata, fingerprints, status |
| `table_checkpoints` | Last PK per table for resume |
| `audit_log` | Per-row/column masking decisions (opt-out via `--no-audit-table`) |

Checkpoints are written every batch (default 10k rows). `privaci resume`
continues from the last checkpoint. Composite-PK tables fall back to
table-level done/not-done checkpoints.

## Masking tiers

| Level | Mechanism | When |
|-------|-----------|------|
| L1 | Column rules (`fake`, `regex_mask`, `hash`, …) | Always |
| L2 | SpaCy NER (`ner_mask`) | Text columns, optional |
| L3 | LLM refinement (`ai_refine`) | Commercial plugin only |

Auto-detect (`auto_detect: true`) scans column names and sample values to
propose rules. See ADR-0011 for confidence scoring.

## Configuration

`mask-rules.yaml` is validated by pydantic at load time. Unknown keys are
rejected. The JSON Schema is exported via `privaci schema config` and
regenerated into [`generated/configuration-reference.md`](../generated/configuration-reference.md).

## Commercial split

The public engine (`privaci`, ELv2) ships with community fallbacks for license
validation, metering, LLM, and reports. The proprietary layer registers
implementations under the `privaci.plugins` entry-point group. See
[Building a plugin](../extending-privaci.md).

## Security constraints

- No PII in logs, errors, or metrics (redaction in `privaci.observability`).
- No intermediate masked data on disk.
- Salt is required at startup; no silent default.
- SQL uses parameterized queries; dynamic identifiers come from catalog
  introspection only.

Report vulnerabilities per [`SECURITY.md`](https://github.com/BoundaryLogic/privaci/blob/main/SECURITY.md).
