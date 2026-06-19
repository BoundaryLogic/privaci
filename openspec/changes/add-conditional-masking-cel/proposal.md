## Why

Column rules today apply uniformly to every row. Real schemas mix nullable
status fields, soft-delete flags, and role-specific columns where masking
should run only when a predicate holds (e.g., mask `notes` only when
`status = 'closed'`). Hand-rolling predicates in application code defeats
the declarative config model and breaks auditability.

Common Expression Language (CEL) is a safe, typed expression language with
mature Python bindings (`cel-python`). A sandboxed `when:` guard on column
rules lets Growth-tier customers express row-level conditions without
arbitrary Python in config files.

## What Changes

- **Optional `when:` on column actions** — CEL expression evaluated per row
  before the action runs. If false, the column value passes through unchanged
  for that row.
- **Typed row context** — CEL environment exposes column names and types from
  the catalog snapshot (`bool`, `int`, `float`, `string`, `bytes`, `null`).
  No database access, no network, no imports.
- **Sandbox limits** — expression size cap, evaluation timeout, no external
  functions beyond a small stdlib (comparisons, string ops, `has()`, ternary).
- **Tier gating:** Growth+ required; starter/community exit `5` when any
  `when:` is present.
- **Validation at boot** — compile CEL at config load; type-check against
  catalog; fail exit `3` with column path and CEL error.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `config-yaml`: Optional `when` string on column action models; CEL compile
  at validation when catalog is available (`validate` / pre-flight).
- `masking-pipeline`: Per-row CEL evaluation before action dispatch;
  passthrough when `when` is false; audit records conditional skips.

## Impact

- **Code:** `src/privaci/config/actions.py`, new `src/privaci/cel/` sandbox
  module, `src/privaci/mask/engine.py`.
- **Dependencies:** `cel-python` (pinned via `pip-compile`).
- **Docs:** `docs/configuration.md` (`when` syntax, examples), `CHANGELOG.md`.
- **Tests:** ReDoS/timeout tests, type-mismatch validation, per-row passthrough.
- **Performance:** CEL eval per masked column per row — acceptable for Growth
  workloads; document cost in wide-table scenarios.
