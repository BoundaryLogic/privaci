#!/usr/bin/env bash
# Pre-push hook: run public integration capabilities for high-risk engine paths.
#
# The quick capability suite is intentionally unit-only. Changes to schema,
# preflight, pipeline, stream, or config code can break live Postgres behavior,
# so gate those pushes with the public capability suite (unit + integration).
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
  echo "capability pre-push: no committed changes to inspect."
  exit 0
fi

high_risk_regex='^(src/privaci/(cli|config|pipeline|preflight|schema|stream)/|tests/(integration|pipeline|preflight|schema|stream)/|scripts/capability_test/)'
if ! printf '%s\n' "$changed_paths" | grep -Eq "$high_risk_regex"; then
  echo "capability pre-push: no integration-sensitive paths changed."
  exit 0
fi

echo "capability pre-push: integration-sensitive paths changed:"
printf '%s\n' "$changed_paths" | grep -E "$high_risk_regex" | sed 's/^/  - /'

# Local workspaces often have the plugin package installed for commercial-unit
# capability checks. The public integration suite is not testing licensing, so
# use the documented local development bypass when that package is present.
if python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("privaci_commercial") else 1)
PY
then
  export PRIVACI_COMMERCIAL_DEV_LICENSE="${PRIVACI_COMMERCIAL_DEV_LICENSE:-1}"
fi

exec ./scripts/capability-test-suite.sh public --allow-heavy
