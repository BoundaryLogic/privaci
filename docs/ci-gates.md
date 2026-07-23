# CI gates and constitution enforcement

Maps [`CONSTITUTION.md`](https://github.com/BoundaryLogic/privaci/blob/main/CONSTITUTION.md)
articles to local and GitHub
checks. Hard is the default for automatable articles.

How gates fit the broader confidence model (threat model → tests → nuclear
checkpoints): [`quality-evidence.md`](quality-evidence.md).

## Modes

| Mode | Meaning |
| --- | --- |
| **Hard** | Required; merge / `ci-local` fails |
| **Ratchet** | Soft ≤1 merge cycle with tracking issue, then hard |
| **Review** | Checklist / nuclear only |

## Article → gate

| Article | Hard gates | Review-only |
| --- | --- | --- |
| I Trust / VPC | HTTP import ban on mask/stream/pipeline; offline mask unit test; AST/Semgrep | Future telemetry intent |
| II Fail closed | Tests + AST/Semgrep (no silent passthrough) | New exit-code naming |
| III PII hygiene | gitleaks (pre-commit + default `ci-local` + `lint-and-test`); Security AST logging bans; audit tests | Novel log shapes |
| IV Memory | Streaming tests; file/function limits; agent resource scripts | Bench regressions |
| V No shortcuts | Required status checks; TODO/waiver issue guard | Nuclear judgment |
| VI Secure defaults | pip-audit; Dependabot; Scorecard (Pinned-Dependencies + Token-Permissions); Trivy/hadolint/actionlint via **Hygiene gate** (`container-hygiene`); CodeQL (GitHub default setup); SQL AST + allowlist; Semgrep; SHA-pinned Actions on **all** workflows including release/docs/PyPI; least-privilege ``GITHUB_TOKEN`` (workflow ``contents: read``, write scopes only on jobs that need them — see [release-infrastructure](runbooks/release-infrastructure.md); Scorecard SARIF via [scorecard.yml](https://github.com/BoundaryLogic/privaci/blob/main/.github/workflows/scorecard.yml)) | CVE triage debates |
| VII Honesty | Public language guard; document registry; `generate_docs --check` | Marketing tone |
| VIII Architecture | import-linter; C901; file limits; critical coverage floors; **jscpd duplicate-code** | Boundary redesigns |
| IX Amendments | Constitution registry row; waiver process | Waiver approval |
| X Docs currency | `docs/registry.yaml` coupling; exit-code anchor sync; env-example sync | Prose quality |

## Local commands

```bash
./scripts/ci-local.sh              # default unit gates (incl. Semgrep, MkDocs link
                                   # boundary, workflow parity, registry, typos, gitleaks)
./scripts/check-duplicates.sh      # jscpd on mask/config/secrets/stream (also in default ci-local)
./scripts/ci-local.sh --security   # no-op alias (Semgrep already in default)
./scripts/ci-local.sh --mutation   # cosmic-ray on mask+config (never default)
./scripts/ci-local.sh --docs       # full MkDocs build (needs sibling docs sync)
```

Default `./scripts/ci-local.sh` is sized for a laptop agent budget
(~several minutes with healthy RAM; see `.cursor/rules/resource-safety.mdc`).
Do not treat it as unbounded — CodeQL, Scorecard, and mutation stay CI-only.
## Duplicate code (jscpd)

- Config: [`.jscpd.json`](https://github.com/BoundaryLogic/privaci/blob/main/.jscpd.json) — fail if duplicated lines in scoped
  packages ≥ **1%** (`minLines` 10, `minTokens` 50).
- Scope: `src/privaci/{mask,config,secrets,stream}/`
- Runner: `./scripts/check-duplicates.sh` (requires Node.js 20+ / `npx`)
- Baseline on land: ~0.21% (one small same-file clone in `stream/fetch.py`).
  Ratchet threshold downward when clones are removed (issue [#42](https://github.com/BoundaryLogic/privaci/issues/42) if needed).

## Article I (no egress on masking path)

Hard gates:

1. **HTTP import ban** — `scripts/check_security_ast.py` fails if `mask/`,
   `stream/`, or `pipeline/` import `httpx`, `requests`, `urllib` /
   `urllib.request`, `urllib3`, `aiohttp`, or `http` / `http.client`
   (issue-linked allowlist only).
2. **Packaging import ban** — import-linter owns the import-graph contract;
   Security AST re-checks `privaci_commercial` under `src/privaci/` as
   defense-in-depth (same single AST walk as other rules).
3. **Offline unit test** — `tests/mask/test_offline_mask_path.py` masks with
   network sockets / DNS blocked.
4. **Logging hygiene (Article III)** — Security AST flags logger calls that
   interpolate strings or pass PII-ish positional names in scoped packages.
   Prefer structured `extra={...}` with redacted fields.

## Mutation

- `./scripts/mutation-critical.sh` / `ci-local --mutation` runs **cosmic-ray**
  on `mask/` then `config/` (never default ci-local).
- Weekly GitHub workflow is **warn-only** until kill-score is calibrated
  (target ≥70% killed on each slice); document promotion in this page when
  required.
- Resource budget: keep the workflow under ~45 minutes on GitHub-hosted
  runners; if cosmic-ray cannot meet that after tuning, switch to mutmut with
  the same scope (design D8).

## Complexity ratchet

- Ruff C901 max complexity is **10** today; plan is to ratchet toward **8**
  while burning down `# noqa: C901` / file-limit waivers on issue [#42](https://github.com/BoundaryLogic/privaci/issues/42).

## Document registry

- Manifest: [`docs/registry.yaml`](registry.yaml)
- Checker: `python scripts/check_doc_registry.py`
- Diff bases (D11): staged (pre-commit); merge-base with `main` (`ci-local`);
  `--base-sha` = PR `pull_request.base.sha` (GitHub). Coupling skipped on
  non-PR pushes to `main` (`--skip-coupling`). Fail closed if the local
  merge-base cannot be resolved.
- Waivers: `DOC_REGISTRY_WAIVER: issue #N` on the entry (see registry schema).
- Changelog: default `optional`; `required` only for operator-visible surfaces.

## Active waivers

| Gate | Scope | Issue | Notes |
| --- | --- | --- | --- |
| File/function limits | Seeded baseline oversizes | [#42](https://github.com/BoundaryLogic/privaci/issues/42) | `scripts/file_limit_waivers.txt` — path-only waives **file size**, not functions |
| C901 complexity | `assert_safe_identifiers`, `_dispatch_mask_action` | [#42](https://github.com/BoundaryLogic/privaci/issues/42) | `# noqa: C901` |
| SQL AST allowlist | stream validated-identifier helpers (`path:symbol`) | [#42](https://github.com/BoundaryLogic/privaci/issues/42) | Prefer symbols over line numbers |
| Coverage floors | mask 96%, secrets 92% baseline | [#42](https://github.com/BoundaryLogic/privaci/issues/42) | First-publish exception; burn to 98%+ |
| Mutation | Weekly warn-only | — | Promote after kill-score calibration |

## Coverage floors

Published after measurement (algorithm in OpenSpec / design D6): target 100%
line coverage for `mask/`, `config/`, `secrets/`. Steady-state floors MUST stay
≥98%; first-publish baselines may be lower with a burn-down issue (see table).
Global ≥85%.

| Package | Floor | Burn-down issue |
| --- | --- | --- |
| `src/privaci/mask/` | 96% (baseline measured) | [#42](https://github.com/BoundaryLogic/privaci/issues/42) → 98% → 100% |
| `src/privaci/config/` | 98% | [#42](https://github.com/BoundaryLogic/privaci/issues/42) → 100% |
| `src/privaci/secrets/` | 92% (baseline measured) | [#42](https://github.com/BoundaryLogic/privaci/issues/42) → 98% → 100% |

Floors file: [`ci-gates-floors.toml`](ci-gates-floors.toml). Baseline seed may be
below 98% only on first publish with a burn-down issue (D6 exception).


## How to add a registry row

1. Add an entry under `entries:` in `docs/registry.yaml`.
2. Bind `code:` globs to `docs:` paths.
3. Set `changelog: required` only for operator-visible behaviour.
4. Run `python scripts/check_doc_registry.py` and `./scripts/ci-local.sh`.

## Branch protection

After calibration, require: `lint-and-test`, `integration`, CodeQL (default
setup), Semgrep,
and the **Hygiene gate** job from `container-hygiene.yml` (aggregates
path-filtered Trivy / hadolint / actionlint; no-op success when those paths
are unchanged so the check name stays stable for branch protection).

## Follow-ups

- Private packaging-repo constitution + gate mirror (OpenSpec task 9.3).
- Mutation warn-only → required after kill-score ≥70% on mask and config.
- Coverage burn-down 92/96 → 98 → 100 (issue [#42](https://github.com/BoundaryLogic/privaci/issues/42)).
- C901 max 10 → 8 while retiring `# noqa: C901` waivers.
- Semgrep vs Security AST: AST owns local SQL/logging/packaging/HTTP/eval for
  `SCAN_PACKAGES` (`mask`/`stream`/`secrets`/`config`/`pipeline`; HTTP limited
  to `mask`/`stream`/`pipeline`). Semgrep runs in **default** `ci-local` and the
  PR Semgrep job (`.semgrep.yml` + `--config=auto` + `--error`); fail closed if
  neither the CLI nor Docker is available locally.
- MkDocs link boundary: `check_mkdocs_doc_links.py` fails relative links that
  leave `docs/` (same class as `mkdocs build --strict`). Out-of-tree files use
  absolute GitHub URLs.
- Workflow tool parity: `check_ci_workflow_parity.py` bans `gitleaks-action` and
  advanced `codeql.yml` (org default setup), and pins Semgrep/gitleaks versions
  against pre-commit.
- Dependabot: `docs-build` skips the private commercial clone when
  `COMMERCIAL_REPO_READ_TOKEN` is empty (Dependabot does not see repo secrets
  unless mirrored under Settings → Secrets and variables → Dependabot). Skip is
  based on token presence so maintainer “Re-run” still works. Full site build
  still runs on human PRs with the secret configured.
- Dependabot grouping: pip majors go in one weekly `pip-major` PR (minor/patch
  already grouped); open-PR limits lowered so lockfile PRs do not pile up and
  conflict after each merge. See `.github/dependabot.yml`.
