## Context

Uniform column rules cover most workloads. Operators need conditional masking
without embedding a scripting language in YAML. CEL is designed for policy
guards with deterministic evaluation and no I/O.

## Goals / Non-Goals

**Goals:**

- Optional `when: "<cel>"` on any column action.
- Row context typed from catalog; compile-time type errors where possible.
- Hard sandbox: no DB, filesystem, network, or arbitrary callouts.
- False `when` → passthrough (not `null` unless action is `null`).
- Gate via capability token `conditional_masking` (plugin `LicenseValidator`
  grants the token; commercial packaging decides which subscriptions include
  it).

**Non-Goals:**

- Table-level or run-level CEL (column scope only in v1).
- User-defined CEL functions or macro libraries.
- Cross-row or aggregate expressions (no subqueries, no window functions).
- Replacing SQL `WHERE` subsetting (commercial subsetting remains separate).
- Per-row audit rows for every conditional skip (rollup only — see D7).

## Decisions

### D1. cel-python (`celpy`) with custom environment

**Decision:** Use PyPI package `cel-python` (import `celpy`) with a restricted
activation record built from the current row. Register only safe builtins:
comparisons, logical ops, `size()`, and string `contains` / `startsWith` /
`endsWith`. Do **not** expose `has()` — activations always bind annotated
columns (including null), so `has(col)` would be always-true and `!has(col)`
would silently under-mask; operators use `col != null` instead.

**Alternatives:** Restricted Python `eval` (unsafe). Jinja2 (not typed).
SQL fragments (injection risk). Rust-backed `common-expression-language`
(faster; defer unless `cel-python` fails perf/sandbox gates in spike).

### D2. Two-phase validation

**Decision:**

1. **Config load** (no catalog): reject unknown YAML keys; enforce
   `conditional_masking` capability when any `when` is non-empty; reject
   oversize expressions; syntax-compile CEL (no catalog type-check).
2. **Preflight / validate-with-catalog:** type-check `when` against the table's
   column types; bind only columns that exist on that table.

`privaci validate` without a live catalog SHALL still enforce capability +
syntax; type-check SHALL run when a catalog snapshot is available (same as
other catalog-aware checks).

Cache compiled programs on `MaskingEngine`. Evaluate per row at mask time.

### D3. Passthrough on false

**Decision:** When `when` evaluates false, skip the action entirely — value
unchanged. Auto-detect SHALL NOT apply to that cell for that row (configured
`when` wins). When `when` is absent, behaviour is unchanged.

### D4. Sandbox limits

**Decision:** Max expression length 512 chars; cooperative elapsed budget of
5 ms per row per column after `evaluate` (document that pure-Python CEL cannot
hard-preempt); max AST depth and node count enforced at compile. Allowed
builtins: comparisons, logic, `size`, and string `contains` /
`startsWith` / `endsWith`. Regex (`matches`), comprehensions (`map` / `filter`),
`has()`, field selection, indexing, and `timestamp`/`duration` are rejected.

### D5. Capability gate (not tier-name matching)

**Decision:** Any non-empty `when` field requires the `conditional_masking`
token in `LicenseStatus.capabilities`. The public engine SHALL NOT match
tier display names. The plugin package’s `capabilities_for_tier` (or equivalent)
grants the token for the subscriptions that include conditional masking.
Community / empty capabilities → exit `5` at config validation (same pattern as
`keyed_actions`).

**Placement:** CEL sandbox and per-row eval live in the **public** engine
(masking pipeline). The plugin package only grants the capability token.

Public OpenSpec / operator docs SHALL name the **capability token** only
(ADR-0007). Subscription product names belong in commercial licensing docs.

### D6. Binary COPY ineligibility

**Decision:** Any in-scope table with at least one non-empty `when` on a
column action is **not** whole-table binary-COPY eligible (must use the batch /
row path so `when` can run). Under `passthrough_copy: require_binary`, that
combination SHALL fail preflight with exit **2** naming the table (same
pattern as other binary-ineligible collisions).

### D7. Conditional-skip audit is a rollup

**Decision:** Do **not** write one audit row per skipped cell. After each
table stream (or in the existing per-table audit summary), emit at most one
`column.conditional_skip` event per guarded column with payload
`{expression_hash, skipped_rows, evaluated_rows}` (names finalised in
observability docs). Never include row values or predicate inputs.

Align naming with existing dotted `column.*` event types
(`column.masked`, `column.passed_through`).

### D8. Non-bool and eval errors fail the run

**Decision:** `when` MUST evaluate to a CEL bool. Non-bool results, CEL
runtime errors, and timeout → fail the run (exit **1**), log
`tables.<t>.columns.<c>.when` only (no row PII), mark run failed. Do not
treat non-bool as false.

### D9. Catalog type mapping (fail closed on unsupported)

**Decision:** Map PostgreSQL types into CEL as follows when a column is
referenced by `when`:

| PG family | CEL binding |
| --- | --- |
| bool | bool |
| int2/int4/int8 | int |
| float4/float8 | double |
| numeric | double (document precision loss) or exit **3** if scale risk — prefer exit **3** when referenced |
| text/varchar/char/uuid | string |
| timestamptz/timestamp/date/time | string (ISO-8601 text from driver) |
| bytea | bytes |
| NULL | null |
| jsonb / arrays / composites / ranges / other | **exit 3** at type-check if referenced |

Operators who need JSON predicates use commercial `json_mask` / subsetting, not
CEL v1.

### D10. Resume

**Decision:** No special resume semantics. `when` is re-evaluated for remaining
rows on resume; config_hash already covers expression text changes.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| CPU overhead on wide tables | Document; binary COPY forced off when `when` present |
| Type coercion surprises | D9 fail-closed; validation errors name column path |
| CEL library CVEs / beta status | Pin version; pip-audit; spike task before lock |
| Soft 5 ms timeout | Document; fail closed on overrun |
| Audit volume | D7 rollup only |

## Open Questions

- Expose `row._table` in CEL for multi-table configs? — defer; column names
  are unique per table scope today.
- Switch to Rust CEL if `cel-python` fails perf/sandbox spike — defer with
  spike task.
