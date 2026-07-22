# PrivaCI Project Constitution

Non-negotiables for humans and agents working on this repository.
CI gates exist to **enforce** these articles — see [`docs/ci-gates.md`](docs/ci-gates.md).

Amendments require an ADR update and a PR that changes this file (Article IX).

---

## I. Trust boundary — data stays with the customer

- The engine runs in the **customer environment** (VPC / cluster). Core masking
  MUST NOT require shipping source PII to BoundaryLogic or a third-party SaaS.
- No “phone home” of row data, samples, or raw secrets. Telemetry — if ever
  added — MUST be opt-in, aggregated, and constitution-amended first.
- Opt-in L3 LLM refinement (`ai_refine`) is the only intentional egress of text
  windows; it stays disabled/unwired until fail-closed and documented; never
  default-on.

Related: ADR-0001, ADR-0007.

## II. Fail closed — never silently expose

- Prefer **hard failure** (clear exit code + Context / Cause / Remediation)
  over passthrough of source PII, weaker masking, or “best effort” that looks
  successful.
- No silent downgrade of security semantics to “save the run.”

## III. PII hygiene

- Never log, audit, or exception-embed **raw PII**. Use fingerprints /
  redaction helpers / structured safe fields only.
- No intermediate masked data on disk; transform in memory between streams.
- No hardcoded secrets, salts, or tokens — including tests (synthetic only).

Related: ADR-0004, ADR-0005, ADR-0006, ADR-0010.

## IV. Memory and resource safety

- Bounded memory streaming; no “load the table” shortcuts.
- Agents and local CI MUST respect resource-safety (no parallel heavy jobs;
  use guard scripts). Shortcuts that OOM the machine violate this article.

Related: ADR-0010.

## V. Correctness over speed-to-merge

- No merging with failing required gates, skipped tests, or waivers without an
  **issue number** and owner.
- No “fix in follow-up” for security or integrity bugs on the critical path.
- Nuclear / OpenSpec gates apply when project rules say so — agents do not skip.

## VI. Security engineering defaults

- Parameterized queries / validated identifiers only — no string-concat SQL
  for values.
- No `eval` / `exec` / dynamic `__import__` for user-controlled paths.
- Dependencies pinned; known critical CVEs fail the build.
- Container non-root; secrets via env/backends, never baked into images.

Related: ADR-0013.

## VII. Integrity and honesty

- Deterministic masking given salt/key; document when outputs are not.
- Docs and listing claims MUST match **shipped** behaviour.
- Public-repo language (ADR-0007): plugin-contract framing in engine docs and
  commits — not product-tier marketing.

## VIII. Architecture discipline

- Respect module boundaries (import-linter).
- Complexity and file/function size limits (ratchet via CI).
- Coverage floors on security-critical packages; global ≥85%.

## IX. Amendments

- Changing an article requires an ADR + PR that updates this file and any gate
  that enforced the old rule.
- Temporary waivers: issue-linked, time-boxed, listed in
  [`docs/ci-gates.md`](docs/ci-gates.md) (Active waivers).

## X. Documentation currency

- Behavioural code changes MUST update the operator docs bound by the
  **document registry** (`docs/registry.yaml`) in the **same PR**.
- Generated reference docs MUST stay fresh (`generate_docs.py --check` in
  default `ci-local`).
- New exit codes, CLI flags, config fields, env vars, and secret schemes MUST
  appear in bound pages (and CHANGELOG `[Unreleased]` when user-visible).

---

## Enforcement modes

| Mode | Meaning |
| --- | --- |
| **Hard** | Required CI/pre-commit check; merge blocked on fail |
| **Ratchet** | Soft for ≤1 merge cycle with a tracking issue, then hard |
| **Review** | Human/nuclear checklist only (automation impossible) |

Hard is the default whenever an article can be machine-checked.
