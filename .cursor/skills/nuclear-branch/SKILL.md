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

## Workflow

1. Diff: default `branch changes`; `uncommitted changes` if asked.
2. Short change summary + key paths helps agents.
3. Launch **three** agents in one message (`run_in_background: true`):

   **Option A:** plugin `thermo-nuclear-review-subagent` +
   `thermo-nuclear-code-quality-review-subagent` with Diff, **plus** one
   `generalPurpose` for `nuclear-branch-contracts` (contracts has no plugin
   subagent). Custom-instruct the first two to also apply the expanded nuclear
   branch skill checklists.

   **Option B (simplest):** three `generalPurpose` agents, each following one
   `nuclear-branch-*` skill with Full Repository Path + Diff.

4. Resource-safety: if memory is tight, run contracts after the first two.
5. Synthesize: findings first, dedupe, weight overlaps, brief verdict. Parent
   may fold BugBot PR comments after the triple completes if a PR exists.

## Prompt stubs (Option B)

```text
Follow <repo>/.cursor/skills/nuclear-branch-review/SKILL.md exactly.
Full Repository Path: <path>. Diff: branch changes | uncommitted changes.
Change summary: <…>.
```

```text
Follow <repo>/.cursor/skills/nuclear-branch-quality/SKILL.md exactly.
…
```

```text
Follow <repo>/.cursor/skills/nuclear-branch-contracts/SKILL.md exactly.
…
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
