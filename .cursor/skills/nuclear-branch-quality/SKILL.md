---
name: nuclear-branch-quality
description: >-
  Branch/diff nuclear maintainability review (code-judo, spaghetti, file-size
  growth, deepening on touched modules). Use for nuclear-branch quality or
  incremental nuclear structure review of PR/branch changes (not full-tree).
disable-model-invocation: true
---

# Nuclear Branch Quality

Diff-scoped maintainability. Tree sibling: `nuclear-codebase-quality`.

## Scope

How the **change** is implemented and how it worsens surrounding structure.
Pre-existing mess only if the diff makes it worse or was the natural fix site.

You **may** launch `thermo-nuclear-code-quality-review-subagent`, then enrich —
or run via `generalPurpose`.

## Core prompt

> Deep code quality audit of the branch’s changes. Ambitious code judo. Flag
> shallow/wrong-seam issues in modules the diff touches.

## Standards

Stock thermo quality bar (1k-line growth, spaghetti, wrappers, wrong layer,
canonical helpers, atomicity) **plus** SRP/naming/duplication and light
deepening (deletion test, locality, one-adapter seams) as findings — not a full
HTML architecture report unless asked.

## Approval bar

Do not approve for “tests pass.” Block on missed visible code-judo, unjustified
1k crossing, new spaghetti, wrong-layer/duplicate helpers, leaky abstractions.

Prioritized findings + concrete remedies. Fewer high-conviction comments.

**Severity:** High, Medium, and Low are all ship blockers. Verdict must not be
“approve” / “ready” while any severity remains open. Prefer **Request changes**
until the closeout table can go green (parent fixes or user waives).
