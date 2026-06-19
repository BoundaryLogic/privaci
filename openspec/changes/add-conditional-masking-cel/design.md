## Context

Uniform column rules cover most MVP workloads. Growth customers need
conditional masking without embedding a scripting language in YAML. CEL is
designed for policy guards with deterministic evaluation and no I/O.

## Goals / Non-Goals

**Goals:**

- Optional `when: "<cel>"` on any column action.
- Row context typed from catalog; compile-time type errors where possible.
- Hard sandbox: no DB, filesystem, network, or arbitrary callouts.
- False `when` → passthrough (not `null` unless action is `null`).

**Non-Goals:**

- Table-level or run-level CEL (column scope only in v1).
- User-defined CEL functions or macro libraries.
- Cross-row or aggregate expressions (no subqueries, no window functions).
- Replacing SQL `WHERE` subsetting (commercial `sample_rate` remains separate).

## Decisions

### D1. cel-python with custom environment

**Decision:** Use `cel-python` with a restricted activation record built
from the current row. Register only safe builtins: comparisons, logical ops,
string methods exposed as CEL functions, `has(field)`.

**Alternatives:** Restricted Python `eval` (unsafe). Jinja2 (not typed).
SQL fragments (injection risk).

### D2. Compile at validation, eval per row

**Decision:** Parse and type-check CEL when catalog + config are both
available (pre-flight / `validate`). Cache compiled program on
`MaskingEngine`. Evaluate per row at mask time.

### D3. Passthrough on false

**Decision:** When `when` evaluates false, skip the action entirely — value
unchanged. Audit log records `conditional_skip` with expression hash, not
row values.

### D4. Sandbox limits

**Decision:** Max expression length 512 chars; eval timeout 5 ms per row per
column; max AST depth enforced by cel-python settings.

### D5. Tier gate

**Decision:** Any `when` field requires Growth, Business, or Enterprise tier.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| CPU overhead on wide tables | Document; optional future batch short-circuit |
| Type coercion surprises | Strict catalog types; validation errors name column |
| CEL library CVEs | Pin version; pip-audit gate |

## Open Questions

- Expose `row._table` in CEL for multi-table configs? — defer; column names
  are unique per table scope today.
