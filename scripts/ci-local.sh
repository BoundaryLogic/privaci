#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml locally — run before every commit.
#
# Usage:
#   ./scripts/ci-local.sh                 # lint-and-test (default; pre-commit hook)
#   ./scripts/ci-local.sh --integration   # + Postgres integration (needs Docker)
#   ./scripts/ci-local.sh --docs          # + generate_docs --check + mkdocs build
#   ./scripts/ci-local.sh --helm          # + helm lint
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_INTEGRATION=0
RUN_DOCS=0
RUN_HELM=0
for arg in "$@"; do
  case "$arg" in
    --integration) RUN_INTEGRATION=1 ;;
    --docs) RUN_DOCS=1 ;;
    --helm) RUN_HELM=1 ;;
    -h | --help)
      echo "Usage: $0 [--integration] [--docs] [--helm]"
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
  python scripts/check_public_repo_language.py
  python scripts/check_public_repo_language.py --git-log 30
  pytest --cov=src --cov-report=term-missing --cov-fail-under=85 -m "not integration"

  pip-audit --requirement requirements.txt || true
}

run_integration() {
  pip install -e ".[dev,nlp]"
  python -m spacy download en_core_web_sm
  docker compose -f compose.dev.yml up -d --wait
  trap 'docker compose -f compose.dev.yml down -v' EXIT
  pytest -m "integration and not slow" -q
}

run_docs() {
  pip install -e ".[dev]"
  python scripts/generate_docs.py --check
  mkdocs build --strict
}

run_helm() {
  helm lint deploy/helm/privaci
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

echo "ci-local: all gates passed"
