---
name: nuclear-codebase-quality
description: >-
  Full-codebase nuclear maintainability audit (code-judo, spaghetti, file size,
  wrong-layer helpers, architecture deepening). Use for nuclear-codebase quality,
  nuclear structure review, or harsh full-tree maintainability (not a PR diff).
disable-model-invocation: true
---

# Nuclear Codebase Quality

Full-tree maintainability and deepening. Diff sibling: `nuclear-branch-quality`.

Do **not** launch Diff-scoped plugin thermo subagents.

## Scope (required)

1. Agree **roots**. Never silent multi-repo scan.
2. Default PrivaCI: `src/privaci/` excluding `spikes/`.
3. Phase by package; prefer files near repo limits and busy orchestration.
4. Resource-safety: scoped search, limited reads.

## Core prompt

> Deep code quality audit of the agreed roots. Improve abstractions, modularity,
> reduce spaghetti. Ambitious code judo. Surface deepening opportunities
> (shallow modules, weak seams, poor locality). Extremely thorough.

## Vocabulary

Use **module / interface / implementation / depth / seam / adapter / locality /
leverage**. Apply the **deletion test**. Prefer findings over a full HTML
architecture report unless the user asks. Honor `CONTEXT.md` / ADRs; mark ADR
conflicts explicitly.

## Standards

0. Ambitious code judo — delete concepts, don’t polish them.
1. File size: **1000+** strong smell; also repo limits (PrivaCI ~400 / ~40) for
   orchestration dumps.
2. No spaghetti / duplicated policy sites.
3. Prefer cleaning design over “it works.”
4. Direct boring code over magic wrappers.
5. Type/boundary cleanliness (`Any`, ad-hoc dicts, silent fallbacks).
6. Canonical layer + reuse helpers.
7. Orchestration / atomicity of multi-step updates.
8. Everyday maintainability: SRP, naming, magic numbers, complexity.
9. Deepening: shallow modules, poor locality, one-adapter fake seams,
   hard-to-test clusters needing a real I/O seam.
10. Perf-as-design when streaming/batching contracts are broken by structure.

## Output

1. Structural debt / wrong-layer / duplicate policy  
2. Missed code-judo / Strong deepening candidates  
3. Spaghetti / branching  
4. Boundary / type / testability seams  
5. File-size / decomposition  
6. Naming / duplication / legibility  

Cleanup backlog, not merge approval. Optional **Top deepening candidate**.
