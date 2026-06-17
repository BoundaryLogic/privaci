#!/usr/bin/env bash
# Selective capability tests — resource-guarded. Unit tests are safe by default.
#
# Safe (no Postgres):
#   ./scripts/capability-test.sh --cap public-detect-drift,commercial-jsonb-transform
#
# Heavy (Postgres / integration — requires healthy RAM and --allow-heavy):
#   ./scripts/capability-test.sh --plan --allow-heavy --cap commercial-subsetting
#   ./scripts/capability-test.sh --allow-heavy --cap commercial-subsetting --no-compose
#
# NEVER combine --reset-volumes with a stressed machine; it tears down and rebuilds DBs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=agent-resource-guard.sh
source "${ROOT}/scripts/agent-resource-guard.sh"

if ! python3.12 -c "import privaci" 2>/dev/null; then
  echo "ERROR: install the public engine first: pip install -e '.[dev]'" >&2
  exit 1
fi

# Always probe memory before starting Python (user cannot interrupt mid-crash).
if ! agent_check_memory; then
  echo "Fix memory pressure first (close browsers, wait for swap to drain)." >&2
  echo "Then: ./scripts/capability-test.sh --plan --cap ..." >&2
  exit 1
fi

agent_apply_limits

exec python3.12 -m scripts.capability_test "$@"
