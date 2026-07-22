## Why

Contributor and agent rules already state non-negotiables (data stays in the
customer environment, fail closed instead of exposing PII, bounded memory, no
merge shortcuts, docs in the same change), but most of that is honour-system.
CI today is strong on format/types/coverage/`pip-audit`, yet lacks a single
constitution, path-coupled documentation enforcement, architecture import
boundaries, critical-path coverage floors, and layered SAST/supply-chain
checks. We need fail-closed gates that encode those principles before more
post-v1 surface area lands.

## What Changes

- **Project Constitution** — root `CONSTITUTION.md` (articles I–X), short ADR,
  always-apply Cursor rule, links from CONTRIBUTING / SECURITY / docs index.
- **Hard-gate policy** — every automatable constitution article maps to a
  required CI/pre-commit check; soft-fail allowed for at most one ratchet cycle
  with an issue; review-only only where automation is impossible.
- **Document registry** — `docs/registry.yaml` + `scripts/check_doc_registry.py`
  fails when code paths change without bound docs/CHANGELOG; promote
  `generate_docs.py --check` into default `ci-local` / `lint-and-test`;
  **exit-code / `default_doc_anchor` sync** against `docs/error-codes.md` in v1.
- **CI hardening stack** — Dependabot, CodeQL, gitleaks, actionlint + Action
  SHA pins, OpenSSF Scorecard, hadolint, PR Trivy, typos, import-linter, ruff
  C901, file-size limits, critical coverage floors (`mask`/`config`/`secrets`
  with locked floor rule), security AST (seeded SQL allowlist) + Semgrep,
  Article I offline/no-egress checks for mask path, weekly **cosmic-ray**
  mutation on `mask/` + `config/` only.
- **Docs** — `docs/ci-gates.md` maps jobs → constitution articles; CHANGELOG
  `[Unreleased]`.
- **Out of scope here:** mirroring the full stack into the private packaging
  repository (tracked as an explicit follow-up after public gates are green).

No **BREAKING** changes to engine CLI, config schema, or runtime behaviour.

## Capabilities

### New Capabilities

- `project-constitution`: Canonical non-negotiables (trust boundary, fail
  closed, PII hygiene, memory, no shortcuts, secure defaults, honesty,
  architecture, amendments, documentation currency) and the hard/ratchet/review
  enforcement policy.
- `document-registry`: Machine-readable code→docs map and CI/pre-commit
  coupling checks, including generated-reference freshness, env-example
  coverage, and exit-code / `default_doc_anchor` sync.
- `ci-hardening-gates`: Local (`ci-local`) and GitHub required checks that
  enforce constitution articles (supply chain, SAST, architecture, coverage
  floor algorithm, security AST allowlists, Article I offline/no-egress,
  cosmic-ray mutation schedule).

### Modified Capabilities

_None._ (Runtime product specs unchanged; this change is contributor/CI
contract only.)

## Impact

- **Repo process:** pre-commit, `scripts/ci-local.sh`, `.github/workflows/*`,
  branch-protection required checks (after calibration).
- **New scripts/config:** `check_doc_registry.py`, `check_security_ast.py`,
  `check_file_limits.py`, `docs/registry.yaml`, import-linter / Semgrep /
  Dependabot / CodeQL / Scorecard / mutation workflows.
- **Docs:** `CONSTITUTION.md`, ADR, `docs/ci-gates.md`, CONTRIBUTING/SECURITY
  links, CHANGELOG.
- **Tests:** unit tests for registry and AST checkers; no new engine
  integration markers required for the first public slice.
- **Follow-up:** private packaging repository constitution addendum + gate
  mirror (separate change after public `main` is green).
