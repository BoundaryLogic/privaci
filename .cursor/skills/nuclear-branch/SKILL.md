---
name: nuclear-branch
description: >-
  Branch/diff nuclear triple review (correctness/security, quality/architecture,
  contracts/ops), then synthesize. Use for nuclear-branch, incremental nuclear,
  triple nuclear on a PR/branch, or comprehensive review of changes since main
  (not full-tree).
disable-model-invocation: true
---

# Nuclear Branch

Incremental counterpart to `nuclear-codebase`. Triple review of **branch / PR /
uncommitted** diffs, then synthesize.

**Enforced by** `.cursor/rules/nuclear-branch-before-pr.mdc` before `gh pr create`
(and before pushing a branch intended for review).

| Pass | Skill |
|---|---|
| Correctness / security | `nuclear-branch-review` |
| Quality / architecture | `nuclear-branch-quality` |
| Contracts / ops | `nuclear-branch-contracts` |

## Severity (ship blockers)

**High, Medium, and Low** are all blockers. Do not recommend deferring Medium/Low
to a follow-up unless the user explicitly waives that finding.

## Quality evidence (regression + convergence)

See [`docs/quality-evidence.md`](../../docs/quality-evidence.md).

- Closeout table MUST include a **Regression** column (test path, checker
  command, or gate). A finding is not closed without it (or an explicit
  user waiver quoting “no regression”).
- After the fix batch, at most **one** verification triple. That re-run only
  checks: (1) the **closed set**, (2) clear **regressions** of that set, (3)
  **new Highs**. New Medium/Low that are not regressions → waive with issue
  or one small batch — do not redesign the change.
- Same finding class returning across runs → strengthen the gate/test before
  another full discovery loop.

## Workflow (freeze → one triple → closeout)

1. **Freeze** — stop feature edits for this review. Diff: default
   `branch changes`; `uncommitted changes` if asked / no commits yet.
2. Short change summary + key paths for agents.
3. Launch **three** agents in **one** message (`run_in_background: true`).
   Do not start another nuclear-branch triple until this one fully returns.
   Do not begin implementing fixes until all three have completed.

   **Option A:** plugin `thermo-nuclear-review-subagent` +
   `thermo-nuclear-code-quality-review-subagent` with Diff, **plus** one
   `generalPurpose` for `nuclear-branch-contracts`. Custom-instruct the first
   two to also apply the expanded nuclear branch skill checklists.

   **Option B (simplest):** three `generalPurpose` agents, each following one
   `nuclear-branch-*` skill with Full Repository Path + Diff.

4. Resource-safety: if memory is tight, run contracts after the first two
   **still without fixing** until the third returns.
5. **Synthesize once** — dedupe, weight overlaps, brief verdict. Emit a
   **closeout table** before any code changes:

   `| ID | Severity | Finding | Status | Evidence | Regression |`

6. **Fix batch** — close every open High/Medium/Low (or record user waivers).
   Each row needs verify evidence **and** a Regression entry (test/gate).
7. **At most one closeout re-run** of the triple after the batch is verified
   (closed-set rules above). Do not re-nuclear after every individual patch.
8. **Stale notifications** — if a newer triple was started, ignore late
   completions from the older triple (link the newer agent ids).

Parent may fold BugBot PR comments after the triple completes if a PR exists —
still subject to the severity rule.

## Prompt stubs (Option B)

```text
Follow <repo>/.cursor/skills/nuclear-branch-review/SKILL.md exactly.
Full Repository Path: <path>. Diff: branch changes | uncommitted changes.
Change summary: <…>.
Severity: High, Medium, and Low are all ship blockers — list all three.
```

```text
Follow <repo>/.cursor/skills/nuclear-branch-quality/SKILL.md exactly.
…
Severity: High, Medium, and Low are all ship blockers — list all three.
```

```text
Follow <repo>/.cursor/skills/nuclear-branch-contracts/SKILL.md exactly.
…
Severity: High, Medium, and Low are all ship blockers — list all three.
Do not verdict "Ship" while Medium/Low remain open unless waived.
```

## Vs other skills

| Skill | Scope | Passes |
|---|---|---|
| Plugin `thermos` | Diff | Stock thermo ×2 |
| `nuclear-branch` | Diff | Nuclear ×3 (incl. contracts) |
| `nuclear-codebase` | Tree roots | Nuclear ×3 |
| `nuclear-openspec` | OpenSpec change | Plan-time triple lens (before code) |

## Examples

- `nuclear-branch` → current branch vs main
- `nuclear-branch uncommitted` → working tree only
