#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml locally — run before every commit.
#
# Usage:
#   ./scripts/ci-local.sh                 # lint-and-test + Semgrep + link/parity guards
#   ./scripts/ci-local.sh --integration   # + Postgres integration (needs Docker)
#   ./scripts/ci-local.sh --docs          # + full mkdocs build (generate_docs --check is default)
#   ./scripts/ci-local.sh --helm          # + helm lint
#   ./scripts/ci-local.sh --security      # alias: Semgrep already runs in default
#   ./scripts/ci-local.sh --mutation      # + critical mutation (mask+config; never default)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Pin to Python 3.12 (matches CI and the pinned spacy==3.8.7, which has no
# cp313/cp314 wheel). The machine default may be newer, so prefer an activated
# venv, then the repo .venv, and fail early with clear guidance otherwise.
select_python_312() {
  if [[ -z "${VIRTUAL_ENV:-}" && -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  local ver
  ver="$(python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || echo none)"
  if [[ "$ver" != "3.12" ]]; then
    echo "ci-local: requires Python 3.12 (CI pins 3.12; spacy==3.8.7 has no 3.13/3.14 wheel)." >&2
    echo "  Found: ${ver} at $(command -v python 2>/dev/null || echo 'no python')." >&2
    echo "  Create one: python3.12 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
    exit 1
  fi
  echo "ci-local: using $(python --version) ($(command -v python))"
}
select_python_312

RUN_INTEGRATION=0
RUN_DOCS=0
RUN_HELM=0
RUN_SECURITY=0
RUN_MUTATION=0
for arg in "$@"; do
  case "$arg" in
    --integration) RUN_INTEGRATION=1 ;;
    --docs) RUN_DOCS=1 ;;
    --helm) RUN_HELM=1 ;;
    --security) RUN_SECURITY=1 ;;
    --mutation) RUN_MUTATION=1 ;;
    -h | --help)
      echo "Usage: $0 [--integration] [--docs] [--helm] [--security] [--mutation]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

run_lint_and_test() {
  python -m pip install --upgrade pip
  pip install -e ".[dev]"

  black --check src/ tests/
  isort --check-only --profile black src/ tests/
  ruff check src/ tests/
  mypy src/ --strict
  python scripts/check_pack_key.py
  python scripts/check_contract_version.py
  python scripts/check_implicit_contracts.py
  python scripts/check_git_emails.py
  python scripts/check_public_repo_language.py --full
  python scripts/check_public_repo_language.py --git-log 30
  python scripts/generate_docs.py --check
  python scripts/check_doc_registry.py
  python scripts/check_mkdocs_doc_links.py
  python scripts/check_ci_workflow_parity.py
  python scripts/check_file_limits.py
  python scripts/check_security_ast.py
  ./scripts/check-duplicates.sh
  if command -v typos >/dev/null 2>&1; then
    typos .
  elif command -v pre-commit >/dev/null 2>&1; then
    # pass_filenames=false in .pre-commit-config.yaml so excludes apply.
    pre-commit run typos --all-files
  else
    echo "ERROR: typos required for ci-local parity (install pre-commit hooks or typos-cli)" >&2
    exit 1
  fi
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --source . --no-git -v
  elif command -v pre-commit >/dev/null 2>&1; then
    pre-commit run gitleaks --all-files
  else
    echo "ERROR: gitleaks required for ci-local parity (install pre-commit hooks or gitleaks)" >&2
    exit 1
  fi
  if command -v lint-imports >/dev/null 2>&1; then
    lint-imports
  elif python -c "import importlinter" 2>/dev/null; then
    python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
  else
    echo "ERROR: import-linter required (pip install -e '.[dev]')" >&2
    exit 1
  fi
  pytest --cov=src --cov-report=term-missing --cov-fail-under=85 -m "not integration"
  # Critical-path floors (documented in docs/ci-gates.md; D6 algorithm).
  python scripts/check_coverage_floors.py

  pip-audit --requirement requirements.txt
  # PR always runs Semgrep; keep it in default so local green ⇒ Semgrep green.
  run_semgrep
}

SEMGREP_IMAGE="${SEMGREP_IMAGE:-semgrep/semgrep:1.110.0}"

run_semgrep() {
  local args=(
    scan
    --config=.semgrep.yml
    --config=auto
    --error
    --severity=ERROR
    src/privaci
  )
  if command -v semgrep >/dev/null 2>&1; then
    semgrep "${args[@]}"
    return
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "ci-local: semgrep CLI missing — using ${SEMGREP_IMAGE}"
    docker run --rm -v "$ROOT:/src" -w /src "${SEMGREP_IMAGE}" semgrep "${args[@]}"
    return
  fi
  echo "ERROR: Semgrep required for ci-local parity with the GitHub Semgrep job." >&2
  echo "  Install: pip install semgrep   OR   ensure docker can pull ${SEMGREP_IMAGE}" >&2
  exit 1
}

run_integration() {
  # Exact parity with .github/workflows/ci.yml job ``integration``.
  # Single pytest session — required to catch cross-file session fixture bugs.
  pip install -e ".[dev,nlp]"
  python -m spacy download en_core_web_sm
  # Fresh volumes match a clean GitHub runner (stale local DBs hide failures).
  docker compose -f compose.dev.yml down -v
  docker compose -f compose.dev.yml up -d --wait
  trap 'docker compose -f compose.dev.yml down -v' EXIT
  pytest -m "integration and not slow" -q
}

run_docs() {
  pip install -e ".[dev]"
  # generate_docs --check already ran in lint-and-test; full site build here.
  if [[ ! -d ../privaci-commercial ]]; then
    echo "ERROR: --docs requires a sibling privaci-commercial clone (commercial pages are build-time synced)."
    exit 1
  fi
  COMMERCIAL_DOCS_SOURCE=../privaci-commercial ./scripts/docs_build.sh
}

run_helm() {
  helm lint deploy/helm/privaci
}

run_security() {
  # Kept for scripts/docs that still pass --security; Semgrep already ran in default.
  echo "ci-local: --security is a no-op (Semgrep runs in default lint-and-test)"
}

run_mutation() {
  ./scripts/mutation-critical.sh
}

run_lint_and_test
if [[ "$RUN_INTEGRATION" -eq 1 ]]; then
  run_integration
fi
if [[ "$RUN_DOCS" -eq 1 ]]; then
  run_docs
fi
if [[ "$RUN_HELM" -eq 1 ]]; then
  run_helm
fi
if [[ "$RUN_SECURITY" -eq 1 ]]; then
  run_security
fi
if [[ "$RUN_MUTATION" -eq 1 ]]; then
  run_mutation
fi

echo "ci-local: all gates passed"
