---
name: nuclear-codebase-review
description: >-
  Full-codebase nuclear correctness/security audit (bugs, OWASP, deps, tests,
  perf footguns, PII, operator footguns). Use for nuclear-codebase, nuclear
  correctness on a tree, or deep full-repo bug/security review (not a PR diff).
disable-model-invocation: true
---

# Nuclear Codebase Review

Full-tree correctness and security. Diff-scoped sibling: `nuclear-branch-review`.

Do **not** launch Diff-scoped plugin thermo subagents.

## Scope (required)

1. Agree **roots**. Never silent multi-repo scan.
2. Default PrivaCI: `src/privaci/` excluding `spikes/`.
3. Phase large roots (catalog → config → schema → pipeline → state → cli).
4. Resource-safety: scoped Grep/`path`, no parallel heavy jobs, limited reads.

## Prompt

Security and correctness expert on **existing production code**. Be EXTREMELY
thorough. NOTHING can slip through. Trace call graphs; do not guess.

## Always cover

### A. Correctness / breakage

Cross-module side effects: schema vs stream vs refresh vs resume; config
validators vs runtime gates; catalog fields vs consumers; audit identity vs
emit shapes. Silent no-ops, wrong identity matching, dead policy, DDL order.

### B. Security / leaks

Hardcoded secrets, string-built SQL, PII in logs/errors, privilege escalation,
plugin/entitlement bypasses. Public repo: ADR-0007 language.

### C. OWASP-style pass

1. **Secrets** — `password=`, `secret=`, `token=`, `api_key=`, `AKIA…`,
   `ghp_…`, committed `.env` / keys; `.gitignore` excludes them.
2. **AuthZ** — server-side checks if any HTTP/API surface is in roots.
3. **Injection** — SQL concat, `eval`/`exec`/shell with untrusted input, path
   traversal.
4. **Dependencies** — `pip-audit` (or equivalent) once if safe; critical CVEs
   and unpinned production ranges.
5. **Data exposure** — errors/logs leaking internals or PII.
6. **Transport headers** — only if a web surface is in scope.

### D. Edge / async

Empty/None/Unicode/long strings; races; blocking I/O in async; bare `except`;
missing remediation on `PrivaCIError` paths.

### E. Tests

Happy + negative coverage on critical paths; fixtures that hand-craft fields
introspection would leave empty; multi-schema / resume / re-run gaps. Do not
run full suites unless asked — cite missing tests as findings.

### F. Performance footguns (high-signal)

N+1, unbounded loads, missing batching where streaming is promised. No micro-nits.

### G. Devex / operator / license

Env/docs drift on touched surfaces, contradictory no-op flags, resume assuming
fresh-run invariants, commercial-tier framing in the public engine.

## Method

1. Map public surfaces under roots.
2. Happy + failure + resume/re-run + multi-schema.
3. Secrets/injection Grep; dependency audit if resource-safe.
4. Spot-check tests for risky paths.
5. Cite paths and evidence.

## Output

**High → Medium → Low / residual**. Title, impact, evidence, fix.

End with **What looks solid**, **Suggested fix order**, **Deferred** dimensions.

## Critical rules

No unfinished research. Never inflate priority. No “clean” claim without residuals.
