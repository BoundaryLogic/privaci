#!/usr/bin/env bash
# Mandatory pytest entrypoint for Cursor agents. Refuses unsafe runs *before*
# starting — the user cannot interrupt mid-crash.
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

agent_check_memory
agent_refuse_unless_allowed "$@"
agent_apply_limits

if agent_args_request_integration; then
  TIMEOUT_SEC="$AGENT_INTEGRATION_TIMEOUT_SEC"
else
  TIMEOUT_SEC="$AGENT_UNIT_TIMEOUT_SEC"
  export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} -m not integration"
fi

export PYTEST_ADDOPTS="${PYTEST_ADDOPTS} --tb=short -q"
export PYTEST_XDIST_AUTO_NUM_WORKERS=0

agent_run_with_timeout "$TIMEOUT_SEC" python3.12 -m pytest "$@"
