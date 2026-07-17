---
name: nuclear-codebase
description: >-
  Full-codebase nuclear triple review (correctness/security, quality/architecture,
  contracts/ops), then synthesize. Use for nuclear-codebase, full-repo nuclear,
  comprehensive codebase audit, or triple nuclear on a tree (not a PR diff).
disable-model-invocation: true
---

# Nuclear Codebase

Comprehensive **tree / module-set** audit. Runs three parallel passes, then
synthesizes.

| Pass | Skill |
|---|---|
| Correctness / security | `nuclear-codebase-review` |
| Quality / architecture | `nuclear-codebase-quality` |
| Contracts / ops | `nuclear-codebase-contracts` |

Do **not** use Diff-scoped plugin thermo subagents. Use `generalPurpose` (or the
parent) following those skill files.

## Why three passes

Correctness and quality stay sharp. **Contracts** owns docs↔code, OpenSpec/ADR,
observability shapes, CI/capability matrix, and migration/pin safety — areas that
get under-weighted when folded into a bug hunt.

## Workflow

1. Agree **roots** (default PrivaCI: `src/privaci/`, exclude `spikes/`).
2. Read the three skill files under `.cursor/skills/nuclear-codebase-*/`.
3. Launch **three** background `generalPurpose` agents in **one** message
   (`run_in_background: true`) with repo path, roots, and “follow skill
   verbatim; prioritized findings + evidence.”
4. Resource-safety: no ci-local/full pytest in parallel with the wave. If
   MemAvailable is tight, run contracts **after** the first two finish instead
   of true triple parallel — say so in the synthesis.
5. Synthesize: findings first, dedupe across all three (overlap = higher
   weight), brief verdict, highest-signal items, residuals / deferred.

Do not restate agent summaries wholesale when already visible.

## Prompt stubs

```text
Follow <repo>/.cursor/skills/nuclear-codebase-review/SKILL.md exactly.
Full Repository Path: <path>. Roots: <roots>.
```

```text
Follow <repo>/.cursor/skills/nuclear-codebase-quality/SKILL.md exactly.
Full Repository Path: <path>. Roots: <roots>.
```

```text
Follow <repo>/.cursor/skills/nuclear-codebase-contracts/SKILL.md exactly.
Full Repository Path: <path>. Roots: <roots>.
```

## Examples

- `nuclear-codebase on src/privaci/schema` → triple → synthesize
- `full-repo nuclear` → default roots → triple → synthesize
