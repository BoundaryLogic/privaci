---
name: nuclear-codebase-contracts
description: >-
  Full-codebase nuclear contracts/ops audit: docs↔code drift, OpenSpec/ADR
  drift, observability/audit emit stability, CI/capability matrix gaps,
  migration and engine-pin upgrade safety. Use with nuclear-codebase or when
  reviewing operator contracts for a tree (not a PR diff).
disable-model-invocation: true
---

# Nuclear Codebase Contracts

Third nuclear pass: **contracts between code and everything outside the runtime
call graph** — docs, specs, observability, CI evidence, upgrade paths.

Diff sibling: `nuclear-branch-contracts`.

## Scope (required)

Same roots as the other nuclear-codebase agents. Also read, when present:

- `docs/` (especially configuration, error-codes, observability, deployment)
- `CHANGELOG.md` `[Unreleased]` / recent entries for claimed behaviour
- `openspec/changes/**` active (non-archived) specs/tasks for the area
- `docs/adr/` when behaviour implies a decision
- `scripts/capability_test/` registry + matrix
- State/schema migration paths (`_privaci`, pins, `.engine-pin` in commercial)

Skip dimensions that cannot apply (e.g. no OpenSpec in repo) and list them under
**Deferred**.

## Always cover

### 1. Docs ↔ code drift

Operator-facing docs that claim flags, defaults, order of operations, or
idempotency the code does not implement (or vice versa: shipped behaviour
undocumented). Prefer `docs/configuration.md`, `docs/error-codes.md`,
`docs/observability.md`.

### 2. OpenSpec / ADR drift

Active OpenSpec tasks marked done but unimplemented (or implemented but tasks
open with contradicting design). ADR contradictions only when friction is real
enough to reopen — mark clearly.

### 3. Observability / audit contract

Emit event shapes inconsistent across create vs refresh (or analogues); audit
`event_type` / payload fields unstable or unmatched to docs; missing events for
security-relevant outcomes.

### 4. CI / capability matrix

Features claimed in docs or OpenSpec with no registry entry / matrix cell /
integration coverage. Public vs commercial suite gaps for cross-repo behaviour.

### 5. Migration / upgrade safety

State schema changes without migrate path; resume compatibility; commercial
`.engine-pin` / version sync implications when public engine contracts change.
Flag “operators on old targets break silently” scenarios.

### 6. Public language / publishable docs (repo-specific)

PrivaCI: ADR-0007 banned phrasing in operator docs under roots. Commercial:
publishable-doc policy if those paths are in scope.

## Method

1. List claimed behaviours from docs/OpenSpec for the roots.
2. Spot-check implementation and tests/matrix for each claim.
3. Diff emit/audit docs vs code call sites.
4. Cite paths on both sides of every drift finding (doc + code).

## Output

**High → Medium → Low**. Drift findings need **both** sides evidenced.

End with **Contract coverage map** (which of the six areas were checked) and
**Deferred**.

## Priority guidance

- High: docs promise safety/idempotency/refresh the code cannot deliver; missing
  error-code docs for new exits; matrix gap on a security-critical path.
- Medium: observability asymmetry; OpenSpec task checkbox lies; pin/upgrade
  footguns.
- Low: wording-only doc polish; speculative ADR reopen.
