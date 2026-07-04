#!/usr/bin/env bash
# Mandatory pytest entrypoint for Cursor agents. Refuses unsafe runs *before*
# starting — the user cannot interrupt mid-crash.
#
# For full CI parity before push, run: ./scripts/ci-local.sh
#
# Usage:
#   ./scripts/agent-safe-test.sh tests/cli/test_foo.py
#   AGENT_ALLOW_INTEGRATION=1 ./scripts/agent-safe-test.sh tests/integration/test_foo.py -m integration
#   AGENT_ALLOW_FULL_SUITE=1 ./scripts/agent-safe-test.sh   # user explicitly asked only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck source=agent-resource-guard.sh
source "${ROOT}/scripts/agent-resource-guard.sh"

# Prefer the repo .venv so `python3.12` resolves to the interpreter that has the
# engine + test deps installed (the machine default may be newer than 3.12).
if [[ -z "${VIRTUAL_ENV:-}" && -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

agent_check_memory
agent_refuse_unless_allowed "$@"
agent_apply_limits

# Build the marker as an argv element, not via PYTEST_ADDOPTS: pytest
# whitespace-splits ADDOPTS, so "-m not integration" there becomes "-m not" plus a
# bogus "integration" path. Callers add their own -m for integration runs.
if agent_args_request_integration; then
  TIMEOUT_SEC="$AGENT_INTEGRATION_TIMEOUT_SEC"
  marker=()
else
  TIMEOUT_SEC="$AGENT_UNIT_TIMEOUT_SEC"
  marker=(-m "not integration")
fi

export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} --tb=short -q"
export PYTEST_XDIST_AUTO_NUM_WORKERS=0

agent_run_with_timeout "$TIMEOUT_SEC" python3.12 -m pytest "${marker[@]}" "$@"
