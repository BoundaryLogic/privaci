#!/usr/bin/env bash
# Run predefined capability suites (quick, standard, full, …).
#
# Capabilities are defined in scripts/capability_test/registry.py. New unit
# capabilities (e.g. public-object-output, public-keyed-pseudonymisation,
# commercial-object-writer) are included automatically in quick/standard via
# the public-unit and commercial-unit groups.
#
# Examples:
#   ./scripts/capability-test-suite.sh quick
#   ./scripts/capability-test-suite.sh standard --allow-heavy --reset-volumes
#   ./scripts/capability-test-suite.sh --allow-heavy full
#   ./scripts/capability-test-suite.sh --list
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

_SUITE_IDS="quick public commercial standard full"

_is_suite_id() {
  local id="$1"
  for known in ${_SUITE_IDS}; do
    [[ "${id}" == "${known}" ]] && return 0
  done
  return 1
}

if [[ $# -eq 0 ]]; then
  set -- standard
fi

case "${1:-}" in
  -h|--help)
    cat <<'EOF'
Usage: capability-test-suite.sh [SUITE] [OPTIONS...]

Suites:
  quick      All unit tests (public + commercial), no Postgres
  public     Public unit + integration
  commercial Commercial unit + integration
  standard   Unit both repos, then public integration, then commercial
  full       Alias for standard

Capabilities: scripts/capability_test/registry.py (--list via capability-test.sh).

Options are forwarded to capability-test.sh (--allow-heavy, --reset-volumes, …).
The suite id may appear before or after flags (e.g. full --allow-heavy).

Examples:
  ./scripts/capability-test-suite.sh quick
  ./scripts/capability-test-suite.sh standard --allow-heavy --reset-volumes
  ./scripts/capability-test-suite.sh --allow-heavy full
EOF
    exit 0
    ;;
  --list)
    exec ./scripts/capability-test.sh --list
    ;;
esac

SUITE=""
FORWARD=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help|--list)
      echo "ERROR: ${1} must be the first argument." >&2
      exit 2
      ;;
    --output-dir)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --output-dir requires a path." >&2
        exit 2
      fi
      FORWARD+=("$1" "$2")
      shift 2
      ;;
    --output-dir=*)
      FORWARD+=("$1")
      shift
      ;;
    --timeout)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --timeout requires a value." >&2
        exit 2
      fi
      FORWARD+=("$1" "$2")
      shift 2
      ;;
    --timeout=*)
      FORWARD+=("$1")
      shift
      ;;
    --cap|--suite)
      echo "ERROR: pass the suite name as a positional argument, not --suite." >&2
      exit 2
      ;;
    quick|public|commercial|standard|full)
      if [[ -z "${SUITE}" ]]; then
        SUITE="$1"
        shift
      else
        echo "ERROR: multiple suite ids: ${SUITE} and $1" >&2
        exit 2
      fi
      ;;
    *)
      FORWARD+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${SUITE}" ]]; then
  SUITE=standard
fi

if ! _is_suite_id "${SUITE}"; then
  echo "ERROR: unknown suite ${SUITE!r}. Use: ${_SUITE_IDS}" >&2
  exit 2
fi

exec ./scripts/capability-test.sh --suite "${SUITE}" "${FORWARD[@]}"
