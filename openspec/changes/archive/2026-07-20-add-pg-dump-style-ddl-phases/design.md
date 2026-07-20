## Context

Today `replicate_schema` applies tables, unique indexes, FKs, functions, views,
and optional matview shells **before** streaming (`src/privaci/schema/replicate.py`,
`objects.py`). Optional matview `REFRESH` and sequence `setval` already run
**after** streaming. Triggers are permanently skipped with `skipped_object`.

ADR-0008 keeps FKs enabled during load (topo order + deferred cycles) so we
cannot disable constraints for speed on managed Postgres. Secondary indexes and
triggers do not have that constraint — they are pure post-load candidates.

Operators recognize PostgreSQL dump sections (`pre-data` / `data` / `post-data`).
Naming phases that way reduces cognitive load vs inventing PrivaCI-only labels.

## Goals / Non-Goals

**Goals:**

- Explicit **pre-data / data / post-data** phases for `schema_mode: replicate`.
- Move **non-unique** indexes (when `replicate_all_indexes: true`) to post-data.
- Keep **PRIMARY KEY / UNIQUE** indexes in pre-data (including unique indexes that
  are not FK targets — integrity + faker UNIQUE awareness during load).
- Replicate **triggers in post-data by default**, with `replicate_triggers: false`
  to skip (audit `skipped_object`).
- Colocate cheap view/function/matview-shell DDL in **post-data** (CREATE cost is
  negligible; one finalize phase beats split timing).
- Preserve ADR-0008 FK-during-load behavior.
- Document phases in operator docs and audit payloads (`ddl_phase`).

**Non-Goals:**

- Moving FKs or PK/UNIQUE to post-data.
- Replicating rules, publications, subscriptions, FDWs, event triggers, or grants.
- Changing `assume_existing` (customer owns all DDL).
- Superuser “session_replication_role” / disable-trigger tricks during load.
- Commercial report redesign beyond optional `ddl_phase` passthrough if already
  collecting schema objects.

## Decisions

### 1. Phase model named like pg_dump

| Phase | Owns |
| --- | --- |
| **pre-data** | Schemas, extensions, sequences (CREATE), tables, partition children, PK/UNIQUE indexes, foreign keys; **plus** functions required by table DEFAULT/CHECK expressions (see Decision 7) |
| **data** | Masked/passthrough row stream (topo layers, deferred cycles); **per-table** `setval` after each table load (unchanged) |
| **post-data** | Non-unique indexes (`replicate_all_indexes`); remaining functions/procedures; plain views; matview shells; triggers (if enabled); matview REFRESH |

**Alternatives:** Keep current “almost everything pre” (rejected — perf + no triggers). Move FKs post (rejected — ADR-0008). Call phases `before_stream`/`after_stream` (rejected — less familiar).

**Note:** Sequence `setval` is **not** a post-data-only concern — it stays tied to each table’s data-phase completion as today (`sync_table_sequences`). Post-data does not re-own setval.

### 2. Unique indexes stay pre-data (Q1)

Even unique indexes that are not FK targets stay pre-data so uniqueness is
enforced during load and UNIQUE-aware masking behavior remains consistent.
Only non-unique indexes move post.

### 3. Triggers default on in post-data (Q2)

`replicate_triggers: true` (default). When false, keep today’s skip + audit.
Trigger functions that are only used by triggers should be created in post-data
before `CREATE TRIGGER` (dependency order). Elevated trigger functions still use
`elevated_objects` dispositions.

**Alternatives:** Default off / opt-in (rejected — user wants post not permanent skip). Always on with no config (rejected — need escape hatch for noisy/broken triggers).

### 4. Views/functions in post-data for simplicity (Q3)

CREATE VIEW/FUNCTION is metadata-cheap; performance does not favor pre vs post.
Putting them in post-data with indexes/triggers yields one **finalize** phase and
avoids “views exist while tables still empty mid-run” surprises for operators
inspecting a live target. Matview shells stay with that phase; REFRESH remains
last among post-data object work (after base tables are loaded).

**Alternatives:** Leave views/functions pre (acceptable perf; worse phase clarity).

### 5. Pipeline hooks and run status

- Keep `replicate_schema` (or rename to `apply_pre_data_ddl`) for pre-data only.
- Add `apply_post_data_ddl` invoked from `stream_and_finish` **after**
  `stream_all_tables` and **before** `finish_run(..., SUCCEEDED)` (same window as
  today’s matview refresh).
- **Success contract:** `RunStatus.SUCCEEDED` SHALL mean pre-data + data +
  post-data all completed. Post-data DDL failure SHALL mark the run `FAILED`
  via the existing `PreflightError` path (**exit 2**, same as pre-data DDL) and
  SHALL NOT emit SUCCEEDED. Operator docs qualify that exit 2 is not only
  "before any writes" when post-data fails after streaming.
- **Resume contract:** On resume, re-run pre-data idempotently, stream remaining
  tables, then always run post-data when all in-scope tables are `done`.
  Post-data DDL MUST be idempotent (`IF NOT EXISTS` / name guards) so a crash
  mid-post-data can retry without re-streaming. No separate durable
  `post_data_pending` flag is required if SUCCEEDED is only written after
  post-data; INTERRUPTED/FAILED runs with all tables `done` simply re-enter
  post-data on resume.

### 6. Audit

`created_object` / `definition_only_object` payloads SHALL include
`ddl_phase: pre-data | post-data`. Trigger create → `created_object` with
`kind: trigger`. Trigger skip → existing `skipped_object`.

### 7. Functions split: DEFAULT/CHECK deps stay pre-data

Column `DEFAULT` and table `CHECK` expressions can reference functions. Those
functions MUST exist before `CREATE TABLE` in pre-data. The engine SHALL:

1. Detect function names referenced by in-scope table DEFAULT/CHECK text
   (best-effort parse / catalog dependency), **or** conservatively treat any
   non-empty `default_expression` that is not `nextval(...)` / identity as
   requiring pre-data function availability.
2. Create required functions in **pre-data** (still honoring `elevated_objects`).
3. Create remaining in-scope functions in **post-data** before views/triggers.

If a DEFAULT/CHECK references an elevated function without disposition,
preflight fails as today (exit **2** / **3** as applicable).

**Alternative considered:** Strip DEFAULTs in pre-data and re-apply in post-data
(more moving parts; rejected for MVP).

### 8. Trigger catalog model (required for implementation)

Today `SkippedObjectInfo` stores only schema/name/parent for triggers — **not**
enough to emit DDL. This change SHALL add a first-class catalog type (e.g.
`TriggerInfo`) populated with at least:

- schema, table, trigger name
- `pg_get_triggerdef(oid, true)` (or equivalent) create statement
- link to the trigger function identity for elevated checks / ordering

Internal triggers (`tgisinternal`) remain excluded (already filtered in
`TRIGGERS_SQL`). Emit path: quote-safe apply of introspected definition in
post-data; failure → run FAILED with actionable error (object name, no PII).

### 9. UNIQUE as constraint vs index

PRIMARY KEY / UNIQUE **table constraints** already emit in `CREATE TABLE`.
Separate UNIQUE **indexes** remain pre-data via `emit_unique_indexes`. No second
system — shared idempotent guards as today.

### 10. Fixed phases (not user-configurable)

Phase membership is an engine invariant. Operators configure *whether* to
replicate (views/functions/triggers/all indexes), not *which phase*. Full
phase overrides are a non-goal (`assume_existing` is the escape hatch).
## Risks / Trade-offs

- **[Risk] Mid-run target looks “incomplete”** (no views/secondary indexes until end) → Mitigate: document phases; `privaci plan` prints phase membership.
- **[Risk] Trigger fires on post-data only — won’t see INSERT during mask** → Acceptable / intended; document that triggers apply to subsequent DML on the target, not to the mask COPY itself.
- **[Risk] Broken SECURITY DEFINER trigger functions** → Mitigate: elevated disposition gate; default still requires explicit elevate for elevated functions.
- **[Risk] Resume edge cases between stream done and post-data done** → Mitigate:
  never mark SUCCEEDED until post-data finishes; resume with all tables `done`
  re-runs idempotent post-data (Decision 5).
- **[Risk] CREATE TABLE fails when DEFAULT references a post-data-only function** →
  Mitigate: Decision 7 — hoist DEFAULT/CHECK-referenced functions into pre-data.
- **[Risk] Trigger catalog lacks DDL today** → Mitigate: Decision 8 — `TriggerInfo`
  + `pg_get_triggerdef` before emit work.
- **[Risk] BREAKING for operators who scraped views before stream finished** → Mitigate: CHANGELOG + docs; rare pattern.

## Migration Plan

1. Ship behind same release as config `replicate_triggers` (default true).
2. CHANGELOG **Changed** + **BREAKING** note for view/function/index timing and triggers.
3. Update `docs/configuration.md` object replication section to the phase table.
4. No config required for existing users except those who must disable triggers
   (`replicate_triggers: false`).

## Open Questions

- None blocking. `privaci plan` phase membership listing is tasked (recommended).
- Deferred (explicit): commercial report `ddl_phase` passthrough — only if collectors
  assume pre-stream object completeness; track in commercial pin follow-up, not
  this engine change.
