#!/usr/bin/env bash
# Pre-push hook: run the exact GitHub ``integration`` job for high-risk paths.
#
# IMPORTANT: do NOT substitute the capability suite here. Capabilities invoke
# pytest per file/capability. That misses cross-file session-fixture bugs
# (e.g. one loader wiping Demo Corp before later e2e tests). GitHub runs:
#
#   pytest -m "integration and not slow" -q
#
# in a single process — this hook must mirror that command via ci-local.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE="${PRIVACI_PREPUSH_INTEGRATION_BASE:-}"
if [[ -z "$BASE" ]]; then
  if git rev-parse --verify --quiet "@{upstream}" >/dev/null; then
    BASE="$(git merge-base "@{upstream}" HEAD)"
  elif git rev-parse --verify --quiet origin/main >/dev/null; then
    BASE="$(git merge-base origin/main HEAD)"
  else
    BASE="$(git merge-base main HEAD)"
  fi
fi

changed_paths="$(git diff --name-only "${BASE}...HEAD")"
if [[ -z "$changed_paths" ]]; then
  echo "integration pre-push: no committed changes to inspect."
  exit 0
fi

# Any path that can change live Postgres behavior or shared integration fixtures.
high_risk_regex='^(\.pre-commit-config\.yaml|\.cursor/rules/integration-before-push\.mdc|scripts/(capability-test-prepush|ci-local)\.sh|scripts/capability_test/|src/privaci/(cli|config|pipeline|preflight|schema|stream)/|tests/(integration|pipeline|preflight|schema|stream)/)'
if ! printf '%s\n' "$changed_paths" | grep -Eq "$high_risk_regex"; then
  echo "integration pre-push: no integration-sensitive paths changed."
  exit 0
fi

echo "integration pre-push: integration-sensitive paths changed:"
printf '%s\n' "$changed_paths" | grep -E "$high_risk_regex" | sed 's/^/  - /'
echo "integration pre-push: running GitHub-parity suite (ci-local --integration)."

# Local workspaces often have the plugin package installed. Public integration
# is not testing licensing; use the documented local development bypass.
if python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("privaci_commercial") else 1)
PY
then
  export PRIVACI_COMMERCIAL_DEV_LICENSE="${PRIVACI_COMMERCIAL_DEV_LICENSE:-1}"
fi

exec ./scripts/ci-local.sh --integration
