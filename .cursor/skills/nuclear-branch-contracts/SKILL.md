---
name: nuclear-branch-contracts
description: >-
  Branch/diff nuclear contracts/ops audit: docs/CHANGELOG/error-codes drift,
  OpenSpec/ADR updates for the change, observability emit stability, capability
  matrix/registry gaps, migration/pin impact. Use with nuclear-branch.
disable-model-invocation: true
---

# Nuclear Branch Contracts

Diff-scoped contracts pass. Tree sibling: `nuclear-codebase-contracts`.

## Scope

Only claims and surfaces **touched by the change** (and docs/specs that should
have been updated with it). Do not boil the ocean on unrelated docs.

## Always cover

1. **Docs ↔ code** — configuration, error-codes, observability, CHANGELOG for
   behaviour in the diff.
2. **OpenSpec / ADR** — active change tasks/design vs what shipped; ADR reopen
   only when the diff forces it.
3. **Observability / audit** — new or changed emit/audit shapes consistent and
   documented.
4. **CI / capability** — registry + matrix cells for new user-facing capability;
   integration gate if paths require it (PrivaCI integration-before-push).
5. **Migration / pin** — state or public contract changes that break resume or
   commercial engine pins.
6. **Public language** — ADR-0007 on touched public paths.

## Output

High → Medium → Low with **doc+code** (or **spec+code**) evidence pairs.
**Contract coverage map** + **Deferred**.

**Severity:** High, Medium, and Low are all ship blockers. Do **not** verdict
**Ship** while Medium or Low findings remain open unless the user has already
waived them. Prefer **Amend then ship** (or **Do not ship**) until the parent
closeout can clear every row. Put true follow-ups (out of scope / future
calibration) under **Deferred** only when they are **not** defects in what this
diff claims to ship — and say so explicitly.
