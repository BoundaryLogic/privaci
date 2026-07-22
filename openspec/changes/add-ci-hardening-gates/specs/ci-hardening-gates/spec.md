## ADDED Requirements

### Requirement: Local and GitHub unit gates stay aligned
`./scripts/ci-local.sh` MUST remain the single local source of truth for
unit-level gates that are safe to run on a contributor laptop. New unit-level
gates introduced by this change (document registry, generate_docs check,
import-linter, C901 via ruff, file limits, security AST, critical coverage
floors, duplicate-code jscpd) MUST be invoked from default `ci-local` and from
GitHub `lint-and-test` (or an explicitly documented equivalent required job).

#### Scenario: Default ci-local includes new light gates
- **WHEN** a contributor runs `./scripts/ci-local.sh` with no extra flags
- **THEN** the run includes document-registry, generate_docs `--check`,
  import-linter, complexity/file-limit checks, security AST, duplicate-code
  check, and critical coverage floors (once those tasks have landed)

### Requirement: Supply-chain and SAST workflows exist
The repository MUST provide Dependabot for pip and GitHub Actions; CodeQL for
Python on push/PR to `main` plus schedule; gitleaks in pre-commit and/or CI;
actionlint on workflow changes; OpenSSF Scorecard on a schedule; hadolint and
Trivy (CRITICAL/HIGH fail) on Dockerfile or lockfile-affecting PRs; and a
typos check. After calibration, these MUST be required status checks where
branch protection allows stable required names (including no-op success when
path filters skip a job).

#### Scenario: Dependabot config present
- **WHEN** the supply-chain phase is merged
- **THEN** `.github/dependabot.yml` configures weekly pip and github-actions
  updates

#### Scenario: CodeQL analysis configured
- **WHEN** the SAST phase is merged
- **THEN** GitHub CodeQL default setup analyzes Python on PRs to `main`
  (advanced `codeql.yml` is not used — it conflicts with default setup SARIF
  upload)

### Requirement: Architecture import and size limits
The repository MUST enforce import-linter contracts that prevent forbidden
edges (including mask/stream/catalog importing cli/pipeline, and packaging
imports under `src/privaci`). Ruff MUST enable McCabe complexity (C901) with
an initial max of 10 and a documented ratchet toward 8. A file-limit script
MUST fail files over 400 lines or functions over 40 lines without an
issue-linked waiver. Before the file/function limit check is required on
`main`, the change MUST seed issue-linked waivers for pre-existing offenders
so the gate only blocks new growth.

#### Scenario: Forbidden import fails
- **WHEN** `src/privaci/mask/` imports from `privaci.cli`
- **THEN** import-linter fails in ci-local and CI

#### Scenario: Oversized file fails without waiver
- **WHEN** a newly oversized `src/` file exceeds 400 lines and has no
  file-limit waiver
- **THEN** the file-limit check fails

#### Scenario: Baseline offenders waived
- **WHEN** the file-limit check first becomes required
- **THEN** pre-existing oversize functions/files listed in the seeded waiver
  set do not fail the check

### Requirement: Duplicate code is bounded on critical packages
The repository MUST run a duplicate-code detector (jscpd) on
`src/privaci/mask/`, `config/`, `secrets/`, and `stream/` in default
`ci-local` and GitHub `lint-and-test`. The check MUST fail when duplicated
lines meet or exceed the threshold in `.jscpd.json` (initial threshold 1%,
minimum 10 lines / 50 tokens). Contributors without Node.js MUST see a clear
remediation error from the check script.

#### Scenario: Over-threshold duplication fails
- **WHEN** duplicated lines in the scoped packages are at or above the
  configured threshold
- **THEN** `./scripts/check-duplicates.sh` exits non-zero

#### Scenario: Current baseline under threshold passes
- **WHEN** scoped-package duplication is below the configured threshold
- **THEN** the duplicate-code check exits 0

### Requirement: Critical-path coverage floors
After unit tests, CI MUST fail if coverage for `src/privaci/mask/`,
`src/privaci/config/`, or `src/privaci/secrets/` falls below the floor
published in `docs/ci-gates.md` / `docs/ci-gates-floors.toml`. Floors MUST be
set by the locked algorithm: measure on the coverage-floor PR; use 100 when
measured rounds to 100%; otherwise use max(98, floor(measured)) with a
burn-down issue. **First-publish exception:** if measured is below 98%, the
initial floor MAY equal floor(measured) with a mandatory burn-down issue to
reach 98% then 100%; subsequent PRs MUST NOT lower a published floor without
an Article VIII note. Global coverage MUST remain ≥85%.

#### Scenario: Drop in mask coverage fails
- **WHEN** unit coverage for `src/privaci/mask/` is below the documented floor
- **THEN** the coverage floor step fails the job

#### Scenario: Sub-100 floor records burn-down issue
- **WHEN** measured mask coverage is 98.7% on the floor-setting PR
- **THEN** the published floor is 98 and `docs/ci-gates.md` links an issue to
  restore 100%

### Requirement: Security AST and Semgrep fail closed on banned patterns
A security AST checker MUST fail on `eval`/`exec`/dynamic `__import__`,
`subprocess` with `shell=True`, and documented SQL-concatenation and unsafe
logging patterns within the scoped packages. Before the SQL-concatenation
rule is required, the change MUST seed an issue-linked allowlist of known-safe
identifier/DDL helpers. Semgrep MUST run in CI with `--config=auto` plus local
rules that mirror at least the mask-path eval/HTTP bans (defense in depth).
Security AST remains the required local owner for SQL-concatenation, logging
hygiene, packaging imports, and HTTP bans across `mask`/`stream`/`pipeline`.
Semgrep MUST fail on ERROR severity after calibration (CLI ``semgrep scan``
with ``--error``, matching ``ci-local --security``; GitHub job uses the
same flags via the ``semgrep/semgrep`` container).

#### Scenario: eval in mask path fails AST check
- **WHEN** `src/privaci/mask/` contains an `eval(...)` call
- **THEN** `check_security_ast.py` exits non-zero

#### Scenario: Allowlisted SQL helper does not fail
- **WHEN** a seeded allowlist entry covers a known-safe SQL/identifier helper
- **THEN** the AST SQL-concat rule does not fail that site

### Requirement: Article I no-egress checks for masking path
The repository MUST fail CI when `mask/`, `stream/` (except issue-linked
allowlist), or the core `pipeline/` masking path imports `httpx`, `requests`,
or `urllib.request`. The repository MUST include at least one unit test that
exercises a representative mask path on synthetic fixtures with network
blocked or sockets failing on connect, and that test MUST pass offline.

#### Scenario: httpx import in mask fails
- **WHEN** `src/privaci/mask/` adds `import httpx` without an allowlist entry
- **THEN** the Article I import check fails

#### Scenario: Offline mask path test passes
- **WHEN** the offline mask-path unit test runs with network blocked
- **THEN** the test passes using synthetic fixtures only

### Requirement: Mutation testing is scheduled not per-PR
Mutation testing MUST use cosmic-ray on `src/privaci/mask/` and
`src/privaci/config/` only (mutmut only if cosmic-ray fails the documented
resource budget after tuning). It MUST run on a weekly schedule and
`workflow_dispatch`. It MUST NOT block every PR until a kill-score threshold
is calibrated and documented (initial target ≥70% killed). A script MUST
document how to run the suite locally via `ci-local --mutation` (never
default).

#### Scenario: Weekly mutation workflow exists
- **WHEN** the mutation phase is merged
- **THEN** a scheduled workflow runs cosmic-ray (or documented mutmut
  fallback) on mask and config packages only

#### Scenario: Default ci-local skips mutation
- **WHEN** a contributor runs `./scripts/ci-local.sh` with no flags
- **THEN** mutation testing is not executed

### Requirement: Heavy scanners are opt-in locally
`ci-local` MUST provide `--security` for Semgrep and `--mutation` for the
critical mutation suite. Gitleaks MUST already run in default `ci-local` /
`lint-and-test`. Default `ci-local` MUST NOT run mutation or full CodeQL.

#### Scenario: Default ci-local skips mutation under heavy flag policy
- **WHEN** a contributor runs `./scripts/ci-local.sh` with no flags
- **THEN** mutation testing and CodeQL are not executed
- **AND** gitleaks still runs as part of the default unit gates
