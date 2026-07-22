## 1. Constitution and docs foundation

- [x] 1.1 Author root `CONSTITUTION.md` articles I–X with ADR citations and
      hard/ratchet/review notes
- [x] 1.2 Add ADR `docs/adr/NNNN-project-constitution.md` adopting the
      constitution
- [x] 1.3 Add `.cursor/rules/constitution.mdc` (alwaysApply) pointing at
      `CONSTITUTION.md`
- [x] 1.4 Link constitution from CONTRIBUTING.md, SECURITY.md, docs/README.md,
      and root README
- [x] 1.5 Add `docs/ci-gates.md` with article→gate matrix and how-to for
      registry rows / waivers / allowlists
- [x] 1.5b Add `docs/quality-evidence.md` (threat model → regression tests →
      closed-set nuclear); wire into nuclear-openspec / nuclear-branch skills
- [x] 1.6 Add CHANGELOG `[Unreleased]` entry for constitution + CI program
- [x] 1.7 Add `.github/dependabot.yml` (weekly pip + github-actions)

## 2. Document registry

- [x] 2.1 Create initial `docs/registry.yaml` with meta excludes (`spikes`),
      rows for every other top-level `src/privaci/*` package (docs or
      issue-linked waiver), operator-facing `changelog: required` only where
      appropriate, plus env-example and constitution bindings
- [x] 2.2 Implement `scripts/check_doc_registry.py` (structure, package
      coverage, diff coupling per D11 bases, env-example keys, waiver
      parsing; skip coupling on non-PR main pushes)
- [x] 2.3 Implement exit-code / `default_doc_anchor` sync against
      `docs/error-codes.md` (D15) inside the registry checker
- [x] 2.4 Add unit tests for the registry checker (pass/fail coupling,
      unregistered package, spikes exclude, changelog optional vs required,
      waiver, missing exit-code anchor)
- [x] 2.5 Wire registry check + `generate_docs.py --check` into default
      `scripts/ci-local.sh` and GitHub `lint-and-test`
- [x] 2.6 Add pre-commit hook for staged coupling / registry file changes
- [x] 2.7 Resolve any current drift so registry + generate_docs + exit-code
      sync are green on the branch before requiring the gate
- [x] 2.8 Register new checker tests in `scripts/capability_test/registry.py`
      if they live under `tests/` paths the suite tracks

## 3. Supply chain and SAST

- [x] 3.1 Confirm CodeQL via GitHub default setup for Python (advanced
      `codeql.yml` omitted — conflicts with default-setup SARIF upload)
- [x] 3.2 Add OpenSSF Scorecard workflow
- [x] 3.3 Add gitleaks to pre-commit and/or CI
- [x] 3.4 Document required-check enablement steps in `docs/ci-gates.md`

## 4. Actions, Docker, and PR Trivy

- [x] 4.1 Add actionlint job; SHA-pin Actions where practical
- [x] 4.2 Add hadolint on Dockerfile changes
- [x] 4.3 Add PR Trivy (CRITICAL/HIGH) for Dockerfile/lockfile paths with
      no-op success when paths unchanged
- [x] 4.4 Add typos check (pre-commit or CI)

## 5. Architecture and complexity

- [x] 5.1 Add import-linter contracts and run from ci-local + CI after a
      baseline import graph check on current `main`
- [x] 5.2 Inventory current C901/complexity offenders; enable ruff C901
      (max 10) with issue-linked noqa allowlist for pre-existing hotspots
- [x] 5.3 Inventory files >400 lines and functions >40 lines; seed
      issue-linked waivers for baseline offenders
- [x] 5.4 Implement `scripts/check_file_limits.py` (400/40) with waiver
      format; wire into ci-local + CI only after 5.3 is green
- [x] 5.5 Document ratchet plan toward complexity 8 and waiver burn-down in
      `docs/ci-gates.md`
- [x] 5.6 Add jscpd duplicate-code gate (`.jscpd.json` +
      `scripts/check-duplicates.sh`) on mask/config/secrets/stream; wire
      into default ci-local + lint-and-test; document in `docs/ci-gates.md`

## 6. Critical coverage floors

- [x] 6.1 Measure current line coverage for mask/config/secrets with the same
      pytest invocation as `ci-local`
- [x] 6.2 Apply D6 algorithm; publish floors and any burn-down issues in
      `docs/ci-gates.md` (first-publish exception may be below 98% with #42)
- [x] 6.3 Add coverage floor steps to ci-local + lint-and-test after unit
      pytest

## 7. Security AST, Semgrep, and Article I

- [x] 7.1 Implement `scripts/check_security_ast.py` for banned patterns in
      scoped packages; add unit tests
- [x] 7.2 Inventory and seed SQL-concat allowlist for known-safe
      identifier/DDL helpers; document format in `docs/ci-gates.md`; only
      then hard-require the SQL rule
- [x] 7.3 Implement Article I HTTP import ban for mask/stream/pipeline
      masking path with issue-linked allowlist support
- [x] 7.4 Add offline mask-path unit test (network blocked / socket fail on
      connect) using synthetic fixtures; register in capability suite if
      needed
- [x] 7.5 Wire security AST + Article I import check into default ci-local +
      CI
- [x] 7.6 Add `.semgrep.yml` local rules + CI Semgrep job; calibrate then
      require
- [x] 7.7 Add `ci-local --security` for Semgrep (gitleaks already in default gates)
- [x] 7.8 Document Article I gates in `docs/ci-gates.md`

## 8. Mutation (schedule only)

- [x] 8.1 Spike cosmic-ray on mask+config; record GitHub Actions
      time/memory budget in `docs/ci-gates.md`
- [x] 8.2 If cosmic-ray cannot meet budget after tuning, switch to mutmut
      with the same scope and document the fallback in the PR + ci-gates
- [x] 8.3 Add weekly + workflow_dispatch mutation workflow; warn-only until
      kill-score calibrated (target ≥70%)
- [x] 8.4 Add `./scripts/mutation-critical.sh` and `ci-local --mutation`
      (never default)
- [x] 8.5 Document threshold and promotion-to-required criteria in
      `docs/ci-gates.md`

## 9. Close-out and follow-ups

- [x] 9.1 Verify `docs/ci-gates.md` lists every article with hard/ratchet/
      review mode including D6 floors, D15 exit-code sync, D16 Article I
- [x] 9.2 Run full `./scripts/ci-local.sh` green on the final public branch
- [x] 9.3 Record explicit follow-up: private packaging-repo constitution
      addendum + document registry + gate mirror (out of scope for this
      change)
- [x] 9.4 nuclear-branch before each stacked PR; no merge from the agent
