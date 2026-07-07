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
- Three audit dispositions: `created_object`, `definition_only_object`, `skipped_object`.
- Idempotent table DDL (indexes, FKs) so re-runs and prebuilt partial schemas do not fail.
- `assume_existing` validation with actionable errors (missing table, column type mismatch).

**Non-goals:**

- Replicating triggers during or after load in this change.
- Replicating rules, publications, subscriptions, FDWs, grants.
- Automatic detection/removal of `SECURITY DEFINER` views (warn + skip or fail — see Open
  Questions).
- Commercial report collectors (separate commercial change after engine ships).

## Decisions

### 1. `schema_mode` replaces implicit behaviour

| Mode | DDL | Data load | Completeness owner |
|------|-----|-----------|-------------------|
| `replicate` (default) | Engine applies tiered replication | Per table strategy | PrivaCI, bounded by safe tiers |
| `assume_existing` | Skip `replicate_schema` | `on_existing_data: truncate` typical | Customer |

`assume_existing` still runs preflight validation: every in-scope config table must exist on
target with compatible column types. Missing objects → `PreflightError` (exit 3) by default;
optional `schema_validation: warn` for soft warnings only.

**Alternative considered:** overload `on_existing_data` alone. Rejected — collision policy
(truncate vs fail) is orthogonal to who owns DDL.

### 2. Tiered object replication (replicate mode only)

**Tier 1 — default-on**

- Functions/procedures in dependency order (`pg_depend` / `pg_proc` graph).
- Plain views (`pg_views`, not matviews) after their function and table dependencies.
- Config: `replicate_views: true` (default), `replicate_functions: true` (default).

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
5. functions / procedures (topological sort)
6. views
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

`assume_existing`: no `created_object` for schema objects. Emit `schema.validated` summary
(optional) and per-mismatch `schema.validation_warning` / `schema.validation_error`.

**Alternative considered:** single `object_replication` event with `disposition` field.
Rejected for GRC — separate event types make compliance queries trivial.

### 6. Phased delivery

| Phase | Ships | Commercial coupling |
|-------|-------|---------------------|
| 1 | `assume_existing` + idempotent index/FK | Pin bump only |
| 2 | Functions + views (default-on) + `created_object` | Report collectors required |
| 3 | Matview definition-only + `definition_only_object` | Report section for no-byte-copy proof |

Each phase is independently mergeable; audit taxonomy for phases 2–3 lands with phase 2.

## Risks / Trade-offs

- **[Risk] `SECURITY DEFINER` views bypass masking boundary** → Default: introspect
  `reloptions` / `pg_views` security; skip with `skipped_object` reason
  `security_definer_not_replicated` unless `replicate_security_definer_views: true`.
- **[Risk] Function bodies reference excluded tables** → Pre-flight dependency check;
  fail with named dependency if referent is `strategy: exclude`.
- **[Risk] Matview `REFRESH` on large views is slow** → Opt-in flag; document cost; emit
  timing in run summary.
- **[Risk] `assume_existing` type compatibility false positives** → Compare normalized
  `format_type` strings; allow widening only when explicitly documented.
- **[Risk] Demo Corp e2e asserts views in `skipped_object`** → Update assertions per phase;
  document as audit-only breaking change.

## Migration Plan

1. Ship phase 1 in public engine minor release (e.g. v1.2.0).
2. Update `docs/configuration.md` with `schema_mode` and tier flags.
3. Bump plugin `.engine-pin`; release official container image after engine tag.
4. Commercial follow-up PR: `report_summary` collectors for new audit types.
5. Demo sandbox: optional `schema_mode` in tfvars (not required for engine GA).

Rollback: set `schema_mode: replicate` (default) and `replicate_views: false` restores
near-current behaviour except idempotent DDL (strict improvement, non-breaking).

## Open Questions

- Should `SECURITY DEFINER` views fail the run (strict) or skip with warning (default)?
- Should `assume_existing` validate column order or only name+type?
- Is `schema.validated` a formal audit event type or run-level metadata only?
