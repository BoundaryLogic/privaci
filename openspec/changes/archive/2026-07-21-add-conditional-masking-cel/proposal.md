## Why

Column rules today apply uniformly to every row. Real schemas mix nullable
status fields, soft-delete flags, and role-specific columns where masking
should run only when a predicate holds (e.g., mask `notes` only when
`status = 'closed'`). Hand-rolling predicates in application code defeats
the declarative config model and breaks auditability.

Common Expression Language (CEL) is a safe, typed expression language with
mature Python bindings (`cel-python` / `celpy`). A sandboxed `when:` guard on
column rules lets operators express row-level conditions without arbitrary
Python in config files.

## What Changes

- **Optional `when:` on column actions** — CEL expression evaluated per row
  before the action runs. If false, the column value passes through unchanged
  for that row (auto-detect does not override).
- **Typed row context** — CEL environment exposes column names and types from
  the catalog snapshot with a documented PG→CEL map; unsupported types fail
  at type-check (exit 3) when referenced.
- **Sandbox limits** — expression size cap, evaluation timeout, no external
  I/O or imports.
- **Capability gating:** token `conditional_masking` required when any `when:`
  is present. Community / empty capabilities → exit `5` (same pattern as
  `keyed_actions`). Commercial package grants the token for entitled paid
  tiers (documented only in commercial licensing docs — ADR-0007).
- **Binary COPY:** any table with a `when` is batch-path only;
  `require_binary` + `when` → exit 2.
- **Audit:** rollup `column.conditional_skip` per column (counts + expression
  hash), never per-row payloads.
- **Validation** — capability + syntax at config load; catalog type-check at
  preflight / validate-with-catalog.

## Capabilities

### New Capabilities

_None as a standalone OpenSpec capability id — gating uses the license
capability token `conditional_masking`._

### Modified Capabilities

- `config-yaml`: Optional `when` string on column action models; CEL compile
  at validation when catalog is available (`validate` / pre-flight).
- `masking-pipeline`: Per-row CEL evaluation before action dispatch;
  passthrough when `when` is false; rollup conditional-skip audits.
- `commercial-tier-contract`: Document `conditional_masking` capability gate
  (engine checks membership; does not hard-code tier names).
- `observability` / `state-and-audit`: new `column.conditional_skip` event.

## Impact

- **Code:** `src/privaci/config/` action models, new `src/privaci/cel/` sandbox
  module, `src/privaci/mask/engine.py`, binary-eligibility helper, capability
  validation helper (mirror `keyed_actions`).
- **Dependencies:** `cel-python` (pinned via `pip-compile`) after a short spike
  confirming sandbox + timeout behaviour.
- **Docs:** `docs/configuration.md`, `docs/observability.md`,
  `docs/state-schema.md`, `docs/error-codes.md` as needed, `CHANGELOG.md`.
  Public docs: capability / plugin language only (ADR-0007).
- **Commercial follow-up (same public batch pin):** grant `conditional_masking`
  in `capabilities_for_tier` for `standard` and `compliance`; update
  commercial `docs/licensing-and-entitlement.md`.
- **Tests:** sandbox, type-check, binary-ineligible, missing capability,
  integration conditional mask, capability registry/matrix.
