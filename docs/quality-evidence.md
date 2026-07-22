# Quality evidence model

How PrivaCI builds **justified confidence** that a change is good enough
(not perfect). Nuclear review is a checkpoint — not the definition of quality.

## Layers (in order)

| Layer | When | What it proves |
| --- | --- | --- |
| **Threat model** | OpenSpec `design.md` before code | We named what must never happen and how it is enforced |
| **Tasks + negative tests** | `tasks.md` / implementation | Bypasses and failures are executable, not chat history |
| **CI gates** | Every commit (`ci-local` / GitHub) | Properties hold without an agent in the loop |
| **Nuclear OpenSpec** | Before implement | Design gaps caught before code invents them |
| **Nuclear branch** | Before PR | Diff review against a **closed finding set** |
| **Owned residuals** | PR body / issues | Conscious imperfection with an owner |

## Threat model (required in OpenSpec design)

Every non-trivial change’s `design.md` MUST include a **Threat model** section
(or link a `threats.md` in the same change) with:

1. Trust boundary / invariant (“X must never …”)
2. Attack or fail-open surfaces (examples: SQL/shell shapes, allowlist scope,
   parse/IO errors, CI↔local flag parity, docs claiming behaviour)
3. Enforcement per item: **gate**, **negative test**, or **review-only**
4. Explicit non-goals / accepted residual risk

`nuclear-openspec` fails High if this section is missing or silent on
security-relevant surfaces the change introduces.

## Regression tests

- Machine-checkable threat items → positive **and** negative/bypass tests in
  `tasks.md` before implementation claims done.
- Each High/Medium closed in `nuclear-branch` MUST record a **Regression**
  column entry (test path, checker command, or gate). “Fixed in chat” is not
  closed.

## Nuclear convergence (avoid infinite discovery)

1. First triple → closeout table (closed set).
2. One fix batch with regressions.
3. At most **one** verification triple — only re-checks the closed set and
   **new Highs** (or clear regressions of that set).
4. New Medium/Low on verify that are not regressions → waive with issue **or**
   one small batch — not a redesign of the change.
5. Same finding class returning across runs → strengthen the gate/test; treat
   as a process defect.

See `.cursor/skills/nuclear-branch/SKILL.md` and
`.cursor/rules/nuclear-branch-before-pr.mdc`.

## What “good enough” means for a PR

- Threat model covered (or residuals owned)
- Related gates green (`./scripts/ci-local.sh` and matching GitHub jobs)
- Closed-set nuclear clean (or findings fixed/waived with quotes)
- Docs/CHANGELOG match shipped behaviour

Related: [`ci-gates.md`](ci-gates.md),
[`CONSTITUTION.md`](https://github.com/BoundaryLogic/privaci/blob/main/CONSTITUTION.md),
ADR-0014.
