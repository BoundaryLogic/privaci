## Context

Nuclear codebase audit (2026-07-17) of `src/privaci/` found correctness bugs
masked by synthetic tests, incomplete exclude-FK behaviour, resume/meter
footguns, and docs/OpenSpec drift after harden-review and schema-replication
work. This design turns that backlog into ordered decisions without expanding
product scope (no new connectors, no matview view-on-matview reordering).

Constraints: public-repo language (ADR-0007); plugin-contract UsageMeter
lifecycle; resource-safe CI; no silent breaking of Demo Corp / capability matrix.

## Goals / Non-Goals

**Goals:**

- Make schema replication correct for real CHECK constraints and exclude-FK
  graphs.
- Make resume and metering identity trustworthy.
- Align remediations, observability contracts, and operator docs with code.
- Reduce structural duplication that blocks safe schema-mode growth
  (`table_strategy`, Run lifecycle, catalog/state seams).

**Non-Goals:**

- Commercial report collectors / `.engine-pin` bump (separate release).
- OpenSpec `add-schema-replication-modes` Phase 4 / P3 matrix cells.
- View-depends-on-matview DDL reorder (documented residual).
- Full observability redesign beyond redaction + field honesty.
- Pen-test / load testing.
- Sanitizing or rewriting source function bodies / indexdefs / DEFAULTs beyond
  existing elevated dispositions — source DB remains a trust boundary
  (document only in this change).
- Matview definition-only shells and `definition_only_object` audit/emit
  semantics (`add-schema-replication-modes`).

## Decisions

### 1. CHECK constraint emission uses introspected clause as-is

**Decision:** Store and emit `pg_get_constraintdef` output as a full constraint
body. Emitter becomes
`CONSTRAINT {quoted_name} {definition}` when `definition` already starts with
`CHECK` / `UNIQUE` / etc.; otherwise retain legacy wrap only for fixtures that
pass expression-only text during migration of tests.

**Alternative:** Strip leading `CHECK (` — fragile across PG versions.

**Tests:** Integration table with live CHECK; unit asserts introspected shape
round-trips.

### 2. Exclude FK: skip dangling REFERENCES; implement `null_orphan_fks`

**Decision:** Keep the flag (not **BREAKING** delete).

1. Never emit FK DDL whose `referenced_id` is excluded or not created.
2. When `null_orphan_fks: true`, during stream set referencing FK columns to
   NULL for every loaded row on those columns (excluded parent ⇒ all referents
   absent on target) — only for nullable columns (existing NOT NULL gate
   remains for non-nullable FKs).
3. When flag is false and nullable FKs point at excluded parents, still skip FK
   DDL; document that referential integrity on target is not preserved for those
   edges.
4. **Binary COPY:** any table that must null orphan FK columns SHALL be forced
   onto the named/batch (cell-processing) path — whole-table binary passthrough
   is ineligible for that table while orphan nulling applies (same class of
   constraint as masking). `passthrough_copy: require_binary` SHALL fail
   preflight for such tables rather than silently shipping non-null orphans.

**Alternative:** Delete flag and always fail if any FK references excluded —
rejected; operators already documented the flag.

**Alternative:** Null only “missing” keys via lookup — rejected; excluded
parents are entirely absent, so all FK values on those columns are orphans.

### 3. UsageMeter: one UUID for register and final

**Decision:** Allocate `run_id` via `start_run` (or pre-allocate UUID7 used by
both). Call `register_run` with that id immediately after start. On resume, do
**not** call `register_run` again; `final_meter` still uses the resumed id
(document: resume finalizes an already-registered commercial session if the
plugin cares).

**Alternative:** Generate id before `start_run` and pass in — also fine if
`start_run` accepts optional id.

### 4. Resume requires schema phase complete

**Decision:** If `schema_mode: replicate` and stored schema snapshot is
**absent**, resume SHALL fail (exit **2** preflight/state — document in
`docs/error-codes.md`) with remediation pointing at `--force-restart` or a
fresh target, **not** stream.

If snapshot **is** present: on resume, run idempotent `replicate_schema` before
streaming (safe given IF NOT EXISTS / reverse DROP matviews). Do **not** treat
“optional probe” as best-effort silence — either re-replicate or fail; choose
**re-replicate** for replicate mode.

`assume_existing` resume unchanged aside from shared identity gates.

**Residual:** The schema snapshot is persisted only after successful
`replicate_schema` (and catalog-object audit). A crash after DDL commits but
before snapshot persist leaves the target looking schema-complete while resume
still fails exit **2**. Remediation remains `--force-restart` (or a fresh
target) — fail closed, not stream into an ambiguous mid-phase state.

### 5. Implement `privaci run --force-restart`

**Decision:** Add CLI flag that abandons incomplete target run state (finish or
delete incomplete run row) and **requires** `on_existing_data` in
`{truncate, drop_create}`. If `on_existing_data: fail` (or other unsupported
value), refuse at preflight with exit **2** and remediation to set truncate or
drop_create. Then starts a fresh run. Update all remediations that cited the
flag.

**Alternative:** Docs-only rewrite — rejected; OpenSpec and errors already
promise the flag.

### 6. Canonical table policy helpers first; Run lifecycle deepen second

**Decision:** Phase A — single `table_strategy` + `excluded_table_ids` module
used by replicate, assume_existing, preflight, skipped_audits, objects.
Phase B — introduce `run-lifecycle` module with `open_run` / `stream_run` /
`close_run` absorbing identity, meter, schema prepare, finish/abort, and
`record_event(audit+emit)`. CLI becomes a thin caller.

**Alternative:** Big-bang Run rewrite only — higher regression risk.

### 7. Catalog snapshot split

**Decision:** Pure serialize `CatalogResult → dict` stays catalog-adjacent;
persist/load SQL moves under `state/`. Remove models↔snapshot cycle and
catalog→`RunStatus` dependency.

### 8. Observability contracts follow hardened code

**Decision:** Docs + canonical OpenSpec observability adopt
`***len=N:{sha256[:8]}` (no reversible preview). `commercial_layer_present`
uses `is_commercial_installed()`. Default-redact free-text `message`/`detail`
unless event-specific allowlist. Exit-5 remediation: License Manager /
subscription active — **not** metering endpoint (ADR-0012).

### 9. skipped_object `reason`

**Decision:** Align with OpenSpec SHALL: every skipped_object audit/emit
includes `reason` (use stable tokens: `flag_disabled` for disabled
`replicate_views`/`replicate_functions`, `not_supported` for matviews,
`dependency_excluded`, `elevated_object_skipped`, existing trigger/rule/
publication reasons).

### 10. Streaming checkpoints

**Decision:** Independent tables in a load-plan layer commit per-table (or
small batches) so checkpoints survive sibling failure. Keep single transaction
only for deferred-cycle strongly-connected components (document).

### 11. Identifier safety expansion

**Decision:** `assert_safe_identifiers` covers views, functions, sequences,
index/constraint names before replication DDL.

### 12. Composite UNIQUE masking

**Decision:** Uniqueness suffixing applies only to **single-column** unique
constraints. Composite unique groups do not get independent per-column
uniqueness mutation (document; avoids impossible joint uniqueness hacks in
MVP).

### 13. `drop_create` preserves `_privaci`

**Decision:** `_drop_user_schemas` excludes `_privaci`. Narrowing drops to
only schemas present in the source catalog is a **residual** (not required for
this change); current behaviour may still drop other non-`_privaci` user
schemas on the target under `drop_create`.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Orphan nulling surprises operators | Docs + dry-run/plan callout; only when flag true |
| `--force-restart` destructive | Require truncate/drop_create collision policy |
| Run lifecycle refactor regressions | Capability matrix + integration; phase A helpers first |
| Checkpoint change alters failure atomicity | Spec cycle exception; integration test sibling fail |
| Composite unique behaviour change | Document; add test; CHANGELOG Changed |
| Crash after DDL, before snapshot | Fail resume (exit **2**); `--force-restart` |

## Migration Plan

1. Land Phase 1 correctness (CHECK, exclude FK, meter, resume gate, force-restart)
   behind normal release; CHANGELOG Fixed.
2. Land docs/contract sync same or immediate follow PR.
3. Land structural phases with behaviour-preserving tests.
4. Commercial pin bump remains orthogonal (schema-mode Unreleased features).

Rollback: revert PR; no `_privaci` version bump required for Phase 1 unless
resume gate stores a new marker (prefer reuse snapshot presence).

## Open Questions

- None blocking close-out after nuclear-openspec re-review (2026-07-17).
  Residuals: post-DDL/pre-snapshot crash window; source-schema-only
  `drop_create` narrowing; joint-seed composite unique (out of MVP);
  `definition_only_object` owned by sibling change.
