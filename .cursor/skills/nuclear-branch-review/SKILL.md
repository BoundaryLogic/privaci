---
name: nuclear-branch-review
description: >-
  Branch/diff nuclear correctness and security review (bugs, OWASP, deps, tests,
  perf footguns). Use for nuclear-branch correctness or incremental nuclear bug
  review of PR/branch changes (not full-tree).
disable-model-invocation: true
---

# Nuclear Branch Review

Diff-scoped correctness/security. Tree sibling: `nuclear-codebase-review`.

## Scope

**ONLY** added/modified code in the branch/PR (or uncommitted set if asked).
Trace outside the diff only to validate findings.

Prefer Diff `branch changes`; use `uncommitted changes` when asked.

You **may** launch `thermo-nuclear-review-subagent` for the core pass, then
enrich with C–G — or run this whole skill via `generalPurpose`. Keep the full
checklist.

## Always cover (on the diff)

### A–B. Core nuclear

Breakages, side effects, resume/re-run, security, PII, feature/license leaks,
devex footguns, intended-breakage discipline, no priority inflation.

### C. OWASP on touched surfaces

New secrets; SQL/command/path injection; PII in new logs; `pip-audit` if
requirements changed; authZ on new HTTP routes.

### D. Edge / async

Null/empty/Unicode; races; blocking I/O in async; swallowed errors.

### E. Tests

Happy + negative for new behaviour; fixtures that would hide the bug.

### F. Perf footguns

N+1, unbounded load, broken streaming promises.

### G. License / public language

ADR-0007 clean on touched public docs/src.

## PR discussion

After **your** audit, if a PR exists and you have medium+ findings, check
BugBot/review threads and merge valid extras.

## Output

High → Medium → Low. Evidence + fix. What looks solid. Fix order.

**Severity:** High, Medium, and Low are all ship blockers for the parent
closeout. Do not mark Medium/Low as “optional” or “defer after merge.”
List every finding with a concrete fix; the parent will not ship with open
Medium/Low unless the user waives them explicitly.
