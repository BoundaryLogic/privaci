---
name: nuclear-openspec
description: >-
  Pre-implementation nuclear review of an OpenSpec change (proposal, design,
  specs, tasks). Checks correctness/security, quality/architecture, and
  contracts/ops so footguns are designed out before coding. Use for
  nuclear-openspec, review this openspec, pre-implement nuclear, or when the
  user wants a harsh plan review before /opsx:apply.
disable-model-invocation: true
---

# Nuclear OpenSpec

**Plan-time** counterpart to `nuclear-branch` / `nuclear-codebase`. Same three
lenses — correctness/security, quality/architecture, contracts/ops — applied to
OpenSpec artifacts **before** implementation.

Goal: force the design to answer the questions that nuclear code review would
fail later (resume, identity, PII, wrong layer, docs/matrix drift, upgrade).

**Enforced by** `.cursor/rules/nuclear-openspec-before-implement.mdc` before
`openspec-apply` / first implementation.

Do **not** implement code in this skill. Findings only: amend the OpenSpec (or
explicitly defer with rationale).

## When to use

- After `openspec-propose` / while drafting `design.md` / before `openspec-apply`
- User says: `nuclear-openspec`, `review this openspec`, `pre-implement nuclear`
- Re-review after a major design edit mid-change

## Inputs

1. Resolve the change directory:
   - User named it → `openspec/changes/<name>/`
   - Else ask, or pick the active non-archived change they are discussing
2. Read at minimum:
   - `proposal.md`, `design.md`, `tasks.md`
   - All `specs/**/*.md`
   - `.openspec.yaml` if present
3. Skim related ADRs / `docs/` / existing modules **only** to ground feasibility
   (resource-safe, scoped reads — not a full codebase nuclear).

## Mode

**Default: single thorough pass** covering all three lenses below (OpenSpec
trees are small; triple parallel is usually waste).

**Optional:** for a very large change, launch three `generalPurpose` agents
(correctness / quality / contracts) in one message, each restricted to one
lens, then synthesize — same pattern as `nuclear-codebase`.

## Lens A — Correctness / security

Ask whether the **design** has already decided these (cite the artifact; if
silent → finding):

### Behaviour & edge cases

- Happy path, failure exits, and **re-run / resume / idempotency**
- Multi-schema / dependency order / DROP vs CREATE order
- Config combinations that must be **rejected** vs silently no-op
  (contradictory flags, mode × feature matrix)
- What happens mid-failure (partial DDL, half-written audit)

### Security / PII

- Where source bytes could leak (e.g. copying matview storage)
- Secrets: new env vars, secret URIs, logging redaction
- SQL/DDL identity: schema-qualified names, quote/escape story
- Privilege / elevated objects: default deny? explicit disposition?
- Public-repo language (ADR-0007) if public engine change

### Threats the design should name

- Operator footguns (flags that look on but do nothing)
- Confused deputy / elevated replication
- Audit identity collisions (bare name vs schema-qualified)

### Threat model section (required)

`design.md` MUST include a **Threat model** section (or link `threats.md` in
the same change). See [`docs/quality-evidence.md`](../../docs/quality-evidence.md).

Minimum:

1. Trust boundary / invariant
2. Attack or fail-open surfaces the change introduces
3. Enforcement per item: gate, negative test, or review-only
4. Accepted residual risk / non-goals

**Missing or empty Threat model on a behaviour/security/CI-gate change = High
(Amend then implement).** Trivial doc-only changes may skim and say why a full
section was not needed.

Silence is a defect: “we’ll figure it out in code” on any High item above.

## Lens B — Quality / architecture

- Is there a **code-judo** framing that deletes a whole branch of complexity
  (append-only audit vs UPDATE; shared in-scope helper vs three policy sites)?
- Right **module/layer** ownership called out (catalog vs schema vs pipeline vs
  state)?
- New concepts earning their keep vs thin flags / tri-state booleans
- File/function growth risk: does the design dump special cases into already
  busy orchestration (`runner`, `lifecycle`)?
- Seams/testability: can the risky policy be a pure helper with unit tests?
- Explicit **non-goals** that prevent scope creep — and residuals that must be
  documented as known limitations

## Lens C — Contracts / ops

- Docs that must ship **with** the change (configuration, error-codes,
  observability, CHANGELOG)
- New/changed exit codes → `docs/error-codes.md` task present?
- Observability/audit event names and payload fields specified (stable shapes)?
- Capability **registry + matrix** cells planned for new user-facing behaviour?
- Integration vs unit test obligations called out (especially DDL/resume)?
- Cross-repo follow-ups (commercial pin, report collectors) explicit and **not**
  silently assumed in the public change?
- Migration / state schema / engine-pin impact if contracts change?
- OpenSpec tasks: every High design decision has a task; no orphan “done”
  checkboxes for unimplemented work; phase gates clear

## Method

1. Summarize the change in 3–5 bullets (what ships, what does not).
2. Walk lenses A→B→C against proposal/design/specs/tasks.
3. Cross-check **tasks.md** covers every High/Medium design obligation,
   including a **Verification** block: positive + negative/bypass tests for
   each machine-checkable threat-model item.
4. Spot-check one related existing module or ADR when a claim depends on
   current behaviour (“today we already…”) — verify or flag as unverified.

## Output

### Verdict

One of:

- **Ready to implement** — no High gaps; Mediums documented or tasked
- **Amend then implement** — High gaps listed; do not apply until fixed
- **Re-scope** — goals/non-goals conflict or unsafe as written

### Findings

**High → Medium → Low / residual**

Each finding:

- Title
- Lens (A/B/C)
- Evidence (artifact path + quote or section)
- Why it would fail nuclear later (or hurt operators)
- **OpenSpec fix** — concrete edit to proposal/design/spec/task (not code)

### Task coverage gaps

List design decisions with no task (or tasks with no design backing).

### Suggested amend order

Numbered, smallest safe patch to the OpenSpec first.

## Critical rules

- Do not write production code or mark tasks `[x]` as part of this review.
- Do not rubber-stamp: “looks good” without stating residuals.
- Prefer fewer high-conviction findings over style nits in prose.
- If the change is commercial-only or public-only, enforce the correct language
  and pin/follow-up rules for that repo.

## Examples

User: `nuclear-openspec add-schema-replication-modes`

→ Read that change’s artifacts → triple-lens findings → amend/ready verdict.

User: `review this openspec before we implement`

→ Resolve active change → same.
