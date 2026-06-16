# ADR-0008: Topological-sort FK loading with deferred constraints for cycles

## Status

Accepted — 2026-05-28

## Context

A core promise of PrivaCI is "full referential integrity preserved."
That's harder than one bullet point. Real schemas contain:

- Acyclic FKs (95% of real schemas).
- Self-referential FKs (`employees.manager_id → employees.id`).
- Two-table cycles (`orders → users` and `users → orders`).
- Cross-schema FKs.
- Polymorphic / "soft" FKs (e.g., Rails `commentable_type` +
  `commentable_id`) that the catalog cannot see.

The implementation has to load tables in an order that doesn't violate
constraints, without requiring privileges that managed Postgres tiers
typically don't grant.

Alternatives considered:

- **Disable triggers + foreign keys for the load, re-enable after.**
  Faster, but requires superuser-equivalent privileges on the target.
  AWS RDS / Aurora / Cloud SQL all restrict the necessary grants.
  Rejected on portability grounds.
- **Two-pass load: insert with FKs nulled out, second pass to update.**
  Doubles row writes, pessimistic memory model, doesn't work for
  `NOT NULL` FKs. Rejected.
- **Topological sort + DEFERRED constraints for cycles** — works with
  standard DML grants, leans on PostgreSQL's native deferrable
  constraints. Accepted.

## Decision

After catalog introspection:

1. Build a directed graph: edge from referenced-table → referencing-table.
2. Topologically sort: produce a list of layers (each layer = tables
   with no remaining unresolved dependencies). Load layers in order.
3. **Cycle handling:**
   - Detect strongly connected components (SCC) with size > 1, OR
     self-loops.
   - Select the lowest-cost edge to defer (heuristic: prefer nullable
     FKs with the smallest expected referencing-row count). Emit a
     `cycle_break` audit event naming the deferred edge.
   - Wrap the SCC's tables in a single transaction with
     `SET CONSTRAINTS ALL DEFERRED`.
   - Load all tables in the SCC. Commit the transaction at the end so
     constraints are validated atomically.
4. **Non-deferrable cycles:** If the deferred edge belongs to a
   constraint that is not `DEFERRABLE`, exit `2` at pre-flight with an
   error containing the exact SQL snippet needed to make it
   `DEFERRABLE INITIALLY IMMEDIATE`. We refuse to silently work
   around the schema.
5. **Polymorphic FKs:** Pattern-detect (`<x>_type` + `<x>_id` columns
   with no catalog FK). Emit a `polymorphic_fk_warning` event and
   continue. Document as a known limitation.

## Consequences

### What works

- **Acyclic schemas:** Layer-by-layer load is fast and simple.
- **Self-referential FKs:** Single-table SCC, single-table deferred
  transaction. Works without privileges.
- **Two-table or larger cycles:** Deferred-constraint transaction.
  Works without privileges, provided constraints are `DEFERRABLE`.
- **Cross-schema FKs:** Caught by the graph; treated the same as
  same-schema FKs.

### What doesn't (limitation surface)

- **Non-`DEFERRABLE` constraints in cycles:** Engine refuses to
  proceed. Customer must `ALTER CONSTRAINT` first. We provide the
  exact SQL.
- **Polymorphic FKs:** Engine cannot detect referential integrity
  problems. Audit log warns; manual `seed_alias` config can establish
  cross-column determinism if needed for consistency.
- **Trigger-enforced "FKs":** Not handled. Documented limitation.

### Performance implications

- The deferred-constraint transaction holds for the full duration of
  the cycle's table loads. For large cyclic tables (rare), this
  transaction can be long-lived. Mitigation: cyclic tables are loaded
  with the same per-batch checkpoint model as acyclic tables, so
  resumability works the same way; the difference is that the cycle
  cannot be partially committed.
- For typical schemas (acyclic, with maybe one small cycle), the
  performance cost is negligible.

### Operational implications

- Pre-flight is responsible for verifying every cycle's constraints
  are `DEFERRABLE` before any data writes.
- The audit log records every cycle, every deferred edge, and every
  polymorphic-FK warning so customers and auditors have a complete
  picture.
- Documentation includes a "preparing your source schema for PrivaCI"
  page covering the `DEFERRABLE` requirement.
