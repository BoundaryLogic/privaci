## Context

`privaci run` today calls `replicate_schema` before streaming masked rows. It creates
schemas, tables, sequences, unique indexes, partition children, and foreign keys from the
source catalog snapshot. Views, materialized views, triggers, rules, and publications are
introspected but never applied — each is logged once as `skipped_object` at run start.

Customers with DBA-managed staging schemas need the inverse: assume tables already exist,
validate compatibility, truncate, and load. Customers with greenfield targets need richer
but bounded replication — especially views that are pure `SELECT` over masked base tables,
and the functions those views call.

Materialized views are the sharp edge: copying stored bytes exfiltrates source PII. Definition
replication with `WITH NO DATA` plus optional `REFRESH` after base tables are masked is the
only safe path.

## Goals / Non-Goals

**Goals:**

- Two explicit modes: `schema_mode: replicate | assume_existing`.
- Tiered, safe-by-default object replication in `replicate` mode.
- Dependency-ordered DDL: functions → views → matview definitions → (optional refresh).
- Object audit dispositions: `created_object`, `definition_only_object`, `skipped_object`.
- Assume-existing validation paper trail: `schema.validated` and `schema.validation_failed`.
- Idempotent table DDL (indexes, FKs) so re-runs and prebuilt partial schemas do not fail.
- `assume_existing` name+type validation; binary COPY gated by order eligibility +
  `passthrough_copy`.
- Elevated views/functions: deny by default; explicit per-object `replicate` | `skip`;
  unresolved → fail.

**Non-goals:**

- Replicating triggers during or after load in this change.
- Replicating rules, publications, subscriptions, FDWs, grants.
- Soft-warn schema validation mode (`schema_validation: warn`) — hard-fail only in this
  change.
- Commercial report collectors (separate commercial change after engine ships).

## Decisions

### 1. `schema_mode` replaces implicit behaviour

| Mode | DDL | Data load | Completeness owner |
|------|-----|-----------|-------------------|
| `replicate` (default) | Engine applies tiered replication | Per table strategy | PrivaCI, bounded by safe tiers |
| `assume_existing` | Skip `replicate_schema` | `on_existing_data: truncate` typical | Customer |

`assume_existing` still runs preflight validation: every in-scope config table must exist on
target with compatible column types (**name + type**; physical order is not part of
compatibility). Missing objects or type mismatches → `PreflightError` (exit **2**), after
writing a `schema.validation_failed` audit row when `audit_log` is enabled.

**Collision policy (orthogonal to DDL ownership):** PrivaCI loads are **full reloads of
source values**, including primary-key / identity column values (`OVERRIDING SYSTEM VALUE`
where needed), then `setval` to the streamed max. Therefore:

| `on_existing_data` | Prebuilt empty in-scope tables | In-scope tables with rows |
|--------------------|--------------------------------|---------------------------|
| `fail` (default) | Allowed under `assume_existing` | Hard preflight fail (exit **2**) |
| `truncate` | Truncate then load | Truncate then load |
| `drop_create` | Rejected with `assume_existing` | Rejected with `assume_existing` |
| `append` | Rejected (MVP) | Rejected (MVP) |

Identity / `SERIAL` columns are **not** a separate gate. Absence of auto-increment does
**not** make populated + no-truncate safe: explicit source keys still collide on unique
constraints. Identity only adds a post-load sequence hazard if a future append mode ever
`setval`s from streamed maxima while higher target IDs remain.

**Alternative considered:** overload `on_existing_data` alone. Rejected — collision policy
(truncate vs fail) is orthogonal to who owns DDL.

**Alternative considered:** warn/fail only when identity columns exist. Rejected —
collisions are a key/unique problem, not an identity-only problem.

### 2. Tiered object replication (replicate mode only)

**Tier 1 — default-on**

- Functions/procedures in dependency order (`pg_depend` / `pg_proc` graph).
- Plain views (`pg_views`, not matviews) after their function and table dependencies.
- Config: `replicate_views: true` (default), `replicate_functions: true` (default).
- **Elevated** objects are excluded from default-on behaviour (see Decision 7).

**Tier 2 — opt-in, definition-only**

- Materialized views: fetch `pg_get_viewdef`, emit `CREATE MATERIALIZED VIEW … WITH NO DATA`.
- Never `COPY` or `INSERT` from source matview storage.
- Optional `refresh_materialized_views: true` runs `REFRESH MATERIALIZED VIEW` after all
  in-scope tables complete (re-derives from masked base tables).
- Always `definition_only_object` audit with `contents_copied: false`.

**Tier 3 — skipped**

- Triggers, rules, publications — `skipped_object` with `reason`:
  `unsafe_during_load` | `customer_owned_semantics` | `low_value_footgun`.

### 3. DDL application order (replicate mode)

```
1. schemas, extensions, sequences (existing)
2. tables, partition children (existing)
3. unique indexes (idempotent)
4. foreign keys (idempotent guard)
5. functions / procedures (topological sort; elevated require disposition)
6. views (elevated require disposition)
7. materialized view definitions (WITH NO DATA)
--- stream masked rows (existing pipeline) ---
8. [optional] REFRESH MATERIALIZED VIEW (post-load)
```

Row streaming must not start until steps 1–7 complete for objects in scope. Triggers must
not exist on target during load (customer responsibility in `assume_existing`; in
`replicate` we do not create them).

### 4. Idempotent table DDL

- Unique indexes: wrap `pg_get_indexdef` output with `IF NOT EXISTS` or catch
  `duplicate_table` / `duplicate_object` and continue.
- Foreign keys: check `pg_constraint` for constraint name before `ADD CONSTRAINT`.
- Inline + standalone SG-style footgun does not apply here, but the same principle: never
  assume exclusive ownership of partial pre-existing DDL.

### 5. Audit event taxonomy

| Event | When | Key payload fields |
|-------|------|-------------------|
| `created_object` | DDL applied | `kind`, `object_name`, `depends_on[]` |
| `definition_only_object` | Matview shell only | `kind`, `contents_copied: false`, `refreshed: bool` |
| `skipped_object` | Intentionally not replicated | `kind`, `reason` |
| `schema.validated` | `assume_existing` validation succeeded | `tables_checked`, `passthrough_copy`, counts |
| `schema.validation_failed` | `assume_existing` validation refused load | mismatch identifiers (no PII values) |

`assume_existing`: no `created_object` for schema objects. Always emit durable
`schema.validated` or `schema.validation_failed` when `audit_log` is enabled (write the
failure row on the target connection before exit 2). Stdout `preflight.ok` /
`preflight.fail` remain for operators.

**Alternative considered:** single `object_replication` event with `disposition` field.
Rejected for GRC — separate event types make compliance queries trivial.

**Alternative considered:** success validation as run metadata / stdout only. Rejected —
durable `_privaci.audit_log` evidence is foundational to the product.

### 6. `assume_existing` compatibility vs binary COPY (`passthrough_copy`)

- **Compatibility contract:** every in-scope column exists on target by **name** with a
  **compatible type**. Column **order is not** part of compatibility (DBA staging may
  reorder or append columns).
- **Binary COPY eligibility:** the positional whole-table binary path is safe only when
  source and target have the same column names, types, and physical order. Extra target
  columns (even at the end) make the no-column-list binary path unsafe.
- Config `passthrough_copy` (Phase 1):

  | Value | Behaviour |
  |-------|-----------|
  | `auto` (default) | Prefer binary when eligible; else named batch path |
  | `require_binary` | Ineligible passthrough table → preflight fail |
  | `batch` | Never use binary; always named batch |

- Mid-run unexpected binary COPY errors SHALL fail the run — no silent mid-table path
  switch. Eligibility is decided before streaming the table.

### 7. Elevated views and functions (deny + explicit disposition)

**Terminology:** Prefer **elevated** over loose “SECURITY DEFINER view.” An object is
elevated when:

- a **function/procedure** is `SECURITY DEFINER`, or
- a **view** runs with owner privileges (PostgreSQL default / non-`security_invoker`),
  i.e. not an invoker-rights view.

**Policy (replicate mode, when views/functions are enabled):**

1. Detect all elevated objects in scope.
2. Every detected elevated object MUST have an explicit disposition in config:
   - `replicate` — copy to target; emit `created_object` (payload notes elevated).
   - `skip` — do not migrate; emit `skipped_object` with reason
     `elevated_object_skipped`; continue.
3. Any elevated object with **no** disposition → preflight **fail** (exit 2), naming the
   object. Newly appearing elevated objects after a prior allowlist also fail until
   addressed.

Config shape (map of schema-qualified name → disposition):

```yaml
elevated_objects:
  clinical.patient_access_v: skip
  reporting.executive_summary_v: replicate
```

**`privaci init` / `plan`:** introspect elevated objects; scaffold `elevated_objects: {}`
(never auto-approve); print a prominent ACTION REQUIRED summary listing objects that need
a disposition. Docs call this out prominently (`configuration.md`, init CLI help).

**Alternative considered:** skip-with-warning by default. Rejected — silent incompleteness;
operators may not notice until apps break. Consistent with salt / fail-closed integrity
patterns (ADR-0005), not with soft medium auto-detect heuristics.

### 8. Phased delivery

| Phase | Ships | Commercial coupling |
|-------|-------|---------------------|
| 1 | `assume_existing` + name/type validation + `passthrough_copy` + validation audit events + idempotent index/FK | Pin bump only |
| 2 | Functions + views + elevated dispositions + `created_object` | Report collectors required |
| 3 | Matview definition-only + `definition_only_object` | Report section for no-byte-copy proof |

Each phase is independently mergeable; object disposition audit taxonomy for phases 2–3
lands with phase 2. Phase 1 validation audit types ship with phase 1.

## Risks / Trade-offs

- **[Risk] Elevated views/functions bypass privilege boundary** → Deny by default;
  require explicit `replicate` or `skip` per object; unresolved fails the run.
- **[Risk] Function bodies reference excluded tables** → Pre-flight dependency check;
  fail with named dependency if referent is `strategy: exclude`.
- **[Risk] Matview `REFRESH` on large views is slow** → Opt-in flag; document cost; emit
  timing in run summary.
- **[Risk] `assume_existing` type compatibility false positives** → Compare normalized
  `format_type` strings; allow widening only when explicitly documented.
- **[Risk] Binary COPY silent wrong-column write on reorder** → Order check gates binary;
  `passthrough_copy: auto|batch|require_binary` makes fallback explicit.
- **[Risk] Demo Corp e2e asserts views in `skipped_object`** → Update assertions per phase;
  document as audit-only breaking change.

## Migration Plan

1. Ship phase 1 in public engine minor release (e.g. v1.2.0).
2. Update `docs/configuration.md` with `schema_mode`, `passthrough_copy`, elevated
   dispositions, and tier flags.
3. Bump plugin `.engine-pin`; release official container image after engine tag.
4. Commercial follow-up PR: `report_summary` collectors for new audit types.
5. Demo sandbox: optional `schema_mode` in tfvars (not required for engine GA).

Rollback: set `schema_mode: replicate` (default) and `replicate_views: false` restores
near-current behaviour except idempotent DDL (strict improvement, non-breaking).

## Resolved questions (2026-07-17)

1. **Elevated objects:** Deny by default; per-object `replicate` | `skip`; unresolved or
   newly discovered → fail. Surface in `init`, `plan`, `run`, and docs. Prefer “elevated”
   terminology.
2. **`assume_existing` column order:** Compatibility = name + type only. Physical order
   is a binary-COPY eligibility gate. Ship `passthrough_copy: auto | require_binary |
   batch` in Phase 1 (default `auto`).
3. **Validation paper trail:** Formal audit events for both success (`schema.validated`)
   and failure (`schema.validation_failed`); stdout preflight events retained for ops.
4. **Populated target + no truncate:** Hard fail for in-scope tables with rows under
   `on_existing_data: fail`, whether or not identity/`SERIAL` columns exist. Empty
   prebuilt tables are allowed in `assume_existing` (row presence, not mere table
   existence). No append/upsert without a future explicit mode.
