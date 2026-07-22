## Context

PrivaCI already runs a strong local/CI baseline (`ci-local.sh`: black, isort,
ruff, mypy `--strict`, pytest ≥85%, `pip-audit`, contract/language/pack
guards). Pre-commit mirrors that on `src|tests|scripts`. Release paths add
Trivy, SBOM, and cosign. Documentation rules (`.cursor/rules/documentation.mdc`)
and security ADRs (VPC trust, no PII in state, constant-memory streaming)
exist as prose.

Gaps: no single constitution agents cite; `generate_docs.py --check` is
opt-in via `--docs`; no code→docs coupling; no import-linter / complexity
ratchet / critical coverage floors; limited SAST/supply-chain on every PR
(CodeQL, Scorecard, Dependabot, gitleaks, Semgrep, PR Trivy, actionlint).

This change is **process and tooling only** — no runtime engine behaviour
change. Stacked PRs land gates incrementally so `main` stays green.

## Goals / Non-Goals

**Goals:**

- Publish `CONSTITUTION.md` articles I–X as the north star for humans and agents.
- Make **hard CI the default** for every automatable article; document the
  hard / ratchet / review matrix in `docs/ci-gates.md`.
- Enforce documentation currency via a **document registry** (including
  exit-code anchor sync) and default `generate_docs.py --check`.
- Extend `ci-local` and GitHub workflows so local and remote unit gates stay
  aligned for checks that are safe to run on a laptop.
- Add supply-chain and SAST layers with fail-closed merge policy after brief
  calibration.
- Enforce Article I with import bans + offline mask-path test.
- Weekly **cosmic-ray** mutation on `mask/` + `config/` only (not every PR).

**Non-Goals:**

- SonarQube / commercial SaaS quality platforms.
- LLM “nuclear” review as a CI job.
- Mutation testing on every PR or on the whole tree.
- Runtime product features (subsetting, connectors, etc.).
- Implementing the private packaging-repository mirror inside this change
  (follow-up only; design notes the interface).
- Automated prose-quality grading of docs.

## Decisions

### D1 — Constitution as root `CONSTITUTION.md` + thin ADR

**Choice:** Canonical text at repo root; ADR records adoption; Cursor rule
points at the file (`alwaysApply: true`).

**Alternatives:** Docs-only page (weaker discoverability); duplicate essay in
`.cursorrules` (drift).

**Rationale:** One page humans and agents open first; ADR for history;
`.cursorrules` already long.

### D2 — Hard gates by default; ratchet ≤1 cycle

**Choice:** New scanners may use `continue-on-error` for at most one merged
PR cycle with a tracking issue, then become required. Waivers need issue
number + constitution article id.

**Alternatives:** Permanent soft-fail (becomes theatre); big-bang hard on day
one (can block `main` on noise).

### D3 — Document registry as YAML + Python checker

**Choice:** `docs/registry.yaml` maps `code:` globs → `docs:` paths +
`changelog` policy. `scripts/check_doc_registry.py` enforces:

1. Diff coupling (code touch ⇒ docs/CHANGELOG touch per D11/D14).
2. Package coverage (every `src/privaci/*` top-level package in ≥1 entry or
   explicit waived; `spikes/` meta-excluded per D12).
3. `.env.example` keys mentioned in bound env docs.
4. **Exit-code / `default_doc_anchor` sync** against `docs/error-codes.md`
   (D15) — required in v1, not deferred.

Promote `generate_docs.py --check` into **default** `ci-local` / lint-and-test.
Full MkDocs build stays `--docs` / dedicated CI docs job (needs sibling docs
sync today).

**Alternatives:** Only generated-docs check (misses hand-written operator
pages); CODEOWNERS-only (no fail on missing doc edit).

**Rationale:** Same pattern as capability-test registry — machine-checkable
ownership.

### D4 — Local vs CI-only split (resource safety)

**Choice:** Default `ci-local` gains: generate_docs check, doc registry
(including exit-code sync), MkDocs docs/-boundary link check, CI workflow tool
parity (no gitleaks-action / no advanced codeql.yml), import-linter, C901,
file limits, security AST, critical coverage floors, Article I import ban
check, jscpd, typos, gitleaks, and **Semgrep** (same flags as the GitHub
Semgrep job; Docker image fallback when the CLI is missing). Flags:
`--mutation` (explicit), `--docs` (full mkdocs). `--security` is a no-op alias.
CodeQL (GitHub default setup — advanced workflow conflicts with default SARIF
upload), Scorecard, and mutation remain GitHub-scheduled or CI-only jobs.

**Rationale:** Matches `.cursor/rules/resource-safety.mdc`; agents must not
OOM laptops.

### D5 — Architecture enforcement via import-linter + size/complexity

**Choice:** import-linter contracts (e.g. `mask`/`stream`/`catalog` must not
import `cli`/`pipeline`; no packaging-repo imports under `src/privaci`;
`contracts` is a leaf). Ruff C901 start max complexity **10**, ratchet toward
**8**. `scripts/check_file_limits.py`: fail >400 lines/file or >40
lines/function unless `# FILE_LIMIT_WAIVER: issue #N`. Baseline waivers per
D13 before hard require.

### D6 — Critical coverage floors (locked algorithm)

**Choice:** Line coverage floors for `src/privaci/mask/`, `config/`, and
`secrets/` after unit pytest:

1. Measure current line/branch combined `%` on the coverage-floor PR with the
   same pytest invocation as `ci-local`.
2. Per package: if measured rounds to 100%, floor = **100**. Else floor =
   **max(98, floor(measured))** as an integer percent, and link an issue in
   `docs/ci-gates.md` Active floor waivers to burn back to 100%.
3. **Baseline exception (first publish only):** if measured is below 98%, the
   first published floor MAY equal `floor(measured)` with a mandatory
   burn-down issue to reach 98% then 100%. Subsequent PRs MUST NOT lower a
   published floor without an Article VIII note.
4. Global remains ≥85%.

### D7 — Security AST + Semgrep + SQL allowlist seed

**Choice:** Custom `check_security_ast.py` fail-closed on `eval`/`exec`/
dynamic `__import__`, `subprocess(shell=True)`, heuristic SQL concat, and
logger calls that interpolate PII-ish names without redaction helpers.
Semgrep adds defense in depth (`--config=auto` + local rules + `--error` in
CI and **default** ``ci-local``). AST scope: `mask`, `stream`, `secrets`,
`config`, `pipeline`. Local Semgrep rules: eval on `mask/`; HTTP imports on
`mask`/`stream`/`pipeline`.

**SQL allowlist (required before hard fail):** Seed known-safe sites (at
minimum validated-identifier helpers under `catalog/identifiers.py` and
schema DDL emitters that use quoting helpers). Format: `path:lineno` or
`module:function` + issue number. New concat outside the allowlist fails.
Document in `docs/ci-gates.md`.

### D8 — Mutation: cosmic-ray, weekly, narrow scope

**Choice:** Use **cosmic-ray** (locked). Scope: `mask/` + `config/` only;
`workflow_dispatch` + weekly schedule; local via
`./scripts/mutation-critical.sh` / `ci-local --mutation` only.

**Resource spike:** Prove the job completes within a documented GitHub Actions
time/memory budget on the mutation PR. If cosmic-ray cannot meet that budget
after tuning, document the failure in `docs/ci-gates.md` and switch to
**mutmut** with the same scope and kill-score policy — the only allowed tool
fallback, called out in the mutation PR description.

Kill-score: warn-only for ≥2 weekly runs; then require a documented threshold
(initial target ≥70% killed; adjust once with issue if the first green
baseline is lower).

### D9 — Stacked PR order

1. Constitution + Dependabot + `docs/ci-gates.md` + OpenSpec landing notes  
2. Document registry + generate_docs in default ci-local + exit-code sync  
3. CodeQL + Scorecard + gitleaks  
4. actionlint + SHA pins + hadolint + PR Trivy  
5. import-linter + C901 + file limits  
6. Critical coverage floors (D6 algorithm)  
7. Security AST (seeded allowlist) + Semgrep + Article I offline/no-egress  
8. Weekly cosmic-ray mutation  

Follow-up (other repo): constitution addendum + registry + gate mirror.

### D10 — Public-repo language

**Choice:** Constitution and CI docs use plugin-contract / community vs
plugin-installed wording (ADR-0007). No product-tier or subscription-product
framing in public artifacts this change adds.

### D11 — Diff base for document-registry coupling

**Choice:**

| Context | Diff base |
| --- | --- |
| Pre-commit | Staged files only (index vs HEAD for coupling) |
| `ci-local` | Working tree vs `merge-base` with `origin/main` (fallback: `main`) |
| GitHub PR | `github.event.pull_request.base.sha` … `github.sha` |
| Push to main | **Skip coupling** on non-PR push; still run structure / package / env / generate_docs / exit-code checks |

Fail closed if merge-base cannot be resolved locally (print remediation: fetch
main). Document in `docs/ci-gates.md`.

### D12 — Package coverage exclusions

**Choice:** Top-level package coverage MUST include every `src/privaci/*`
directory except: `spikes/` (explicit `exclude: true` in registry meta),
and `__pycache__`. Internal-only packages still need a registry row (may use
`docs: []` + issue-linked waiver, not silent omission).

### D13 — Size/complexity baseline before hard fail

**Choice:** Before requiring file-limit (400) and function-limit (40) checks,
run an inventory on `main` and seed an issue-linked waiver file (or inline
waivers) for **existing** offenders. New oversizes without waiver fail.
Measured baseline at propose time: ~1 file >400 lines (`cli/app.py` ≈413);
~21 functions >40 lines (mostly pipeline/stream/cli). Ratcheting complexity
C901 similarly starts with an allowlist of current violations.

### D14 — Changelog coupling is not “every code touch”

**Choice:** Registry entries default to `changelog: optional`. Use
`changelog: required` only for operator-visible surfaces (CLI flags, config
schema/actions, exit codes, secrets schemes, deployment). Refactors, test
helpers, and comment-only edits MUST NOT require CHANGELOG. Coupling still
requires a docs path touch when `docs:` is non-empty; for pure-internal
packages with `docs: []` + waiver, only structure checks apply.

### D15 — Exit-code / doc-anchor sync in registry v1

**Choice:** Ship in the document-registry PR. The checker MUST collect every
`PrivaCIError` subclass `exit_code` and `default_doc_anchor` from
`src/privaci/errors.py` and fail if `docs/error-codes.md` lacks a matching
heading/anchor (pattern `exit-code-N-…`). New error classes without a docs
section fail CI.

### D16 — Article I offline / no-egress hard checks

**Choice:** In the security AST/Semgrep phase:

1. **Import ban:** fail if `mask/`, `stream/` (except issue-linked allowlist),
   or core `pipeline/` masking path import `httpx`/`requests`/
   `urllib.request` (secrets backends stay outside this ban).
2. **Unit test:** at least one test exercising a representative mask path on
   synthetic fixtures with network blocked or socket monkeypatched to fail on
   connect — MUST pass offline.
3. Document both under Article I in `docs/ci-gates.md`.

### D17 — Duplicate code (jscpd) on critical packages

**Choice:** Hard gate via `jscpd` (npx, pinned version) on
`mask/`, `config/`, `secrets/`, `stream/`. Config in `.jscpd.json`:
`minLines` 10, `minTokens` 50, fail at ≥ **1%** duplicated lines. Wired into
default `ci-local` and GitHub `lint-and-test` (with `actions/setup-node`).
Requires Node.js locally; fail closed with install remediation if `npx` is
missing. No separate “spaghetti” scanner — C901 + import-linter + file limits
cover structure.

**Alternatives:** Whole-tree scan (noisier); pure-Python detectors (weaker);
report-only (theatre).

## Threat model

Quality evidence: [`docs/quality-evidence.md`](../../../docs/quality-evidence.md).

| Invariant / surface | Fail-open risk | Enforcement |
| --- | --- | --- |
| Security AST miss (`eval`, `shell=True` shapes, SQL concat, HTTP on Article I path) | Merge with banned patterns | `check_security_ast.py` + negative unit tests; Semgrep `--error` defense-in-depth |
| Symbol allowlist hides non-SQL rules | `eval` waived via SQL helper symbol | Allowlist applies to `sql-concat` only; regression test |
| Doc registry / exit-code sync incomplete | Docs drift from `errors.py` | `check_doc_registry.py` (anchors + `exit_code` sections; AnnAssign) |
| `ci-local` ↔ GitHub unit gate drift | Local green, CI red (or reverse) | Same checkers in `ci-local` + `lint-and-test`; Semgrep path/`--error` parity |
| Gate fail-open on IO/parse (`OSError`, `SyntaxError`, empty tree) | Silent skip | Findings / non-zero exit; empty-scan fail-closed when no `.py` under `src/privaci` |
| Coverage floors / file limits / gitleaks / typos missing locally | False local parity | Fail closed if tools missing; floors require canonical TOML keys |
| Public-repo language | Tier/subscription-product framing in engine docs | `check_public_repo_language.py` on constitution/ci-gates/registry |

**Accepted residual:** mutation warn-only until kill-score calibrated; packaging-repo
constitution mirror deferred (task 9.3); release/docs/publish workflows may keep
tag refs; coverage/C901 burn-down via #42.

## Risks / Trade-offs

- **[Noise from Semgrep/CodeQL/Trivy]** → Ratchet ≤1 cycle; triage allowlists
  with issue links; path-filter Trivy to Dockerfile/lockfile PRs.
- **[Doc registry false positives on refactors]** → Default `changelog:
  optional` (D14); DOC_REGISTRY_WAIVER with issue; `spikes/` excluded (D12).
- **[Ambiguous diff base]** → Locked in D11; fail closed with fetch-main
  remediation if merge-base missing.
- **[Existing >40-line functions break CI]** → D13 inventory + seed waivers
  before hard gate.
- **[Coverage below 100%]** → D6 algorithm; floor ≥98% with burn-down issue;
  never silent lower.
- **[SQL AST false positives]** → D7 seeded allowlist before hard require.
- **[cosmic-ray too heavy]** → D8 budget spike; mutmut-only fallback with PR
  callout.
- **[ci-local runtime growth]** → Keep heavy scanners behind flags; time
  budget documented in `docs/ci-gates.md`.
- **[Branch protection churn]** → No-op success when path filters skip Trivy.
- **[Mutation flaky/slow]** → Schedule only; never block PR until calibrated.

## Migration Plan

1. Land constitution docs with no new failing gates (Dependabot only).
2. Green the registry (including exit-code anchors) against current tree
   **before** requiring the check on `main`.
3. Enable each scanner as non-required or soft-fail → fix → required.
4. Apply D6 measurement before publishing coverage floors.
5. Seed SQL + HTTP import allowlists before hard AST require; land offline
   mask test in the same phase.
6. Update branch protection when each gate is calibrated.
7. Rollback: revert the workflow/script PR; constitution docs can remain.

## Open Questions

_None._ Prior nuclear residuals are locked as D6–D8 and D15–D16.
