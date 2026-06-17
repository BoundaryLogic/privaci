#!/usr/bin/env bash
# Shared preflight for agent shell commands. Source, do not execute directly.
# Refuses work when the machine is already under memory pressure — the user
# cannot message the agent mid-crash to stop a runaway command.
set -euo pipefail

# Tunable via env; keep conservative defaults.
: "${AGENT_MIN_AVAIL_MB:=2048}"       # refuse if MemAvailable below this
: "${AGENT_MAX_SWAP_USED_PCT:=80}"     # swap limit when RAM is also tight
: "${AGENT_STALE_SWAP_OK_MB:=8192}"   # skip swap check when MemAvailable >= this
: "${AGENT_IGNORE_SWAP:=0}"            # set 1 to skip swap check entirely
: "${AGENT_MAX_AS_MB:=3072}"          # ulimit virtual memory cap for child
: "${AGENT_UNIT_TIMEOUT_SEC:=90}"     # hard kill for unit test runs
: "${AGENT_INTEGRATION_TIMEOUT_SEC:=180}"

agent_mem_available_mb() {
  free -m | awk '/^Mem:/ { print $7 }'
}

agent_swap_used_pct() {
  free -m | awk '/^Swap:/ {
    if ($2 == 0) { print 0; exit }
    printf "%d", ($3 * 100) / $2
  }'
}

agent_check_memory() {
  local avail swap_pct
  avail="$(agent_mem_available_mb)"
  swap_pct="$(agent_swap_used_pct)"

  if (( avail < AGENT_MIN_AVAIL_MB )); then
    echo "agent-resource-guard: REFUSE — ${avail}MB MemAvailable (need ${AGENT_MIN_AVAIL_MB}MB)." >&2
    echo "Wait for memory to recover before running tests." >&2
    return 1
  fi
  if [[ "${AGENT_IGNORE_SWAP}" == "1" ]]; then
    return 0
  fi
  if (( avail >= AGENT_STALE_SWAP_OK_MB )); then
    return 0
  fi
  if (( swap_pct > AGENT_MAX_SWAP_USED_PCT )); then
    echo "agent-resource-guard: REFUSE — swap ${swap_pct}% used with only ${avail}MB MemAvailable." >&2
    echo "Need ${AGENT_STALE_SWAP_OK_MB}MB free to ignore stale swap, or set AGENT_IGNORE_SWAP=1." >&2
    echo "Or clear swap: sudo swapoff -a && sudo swapon -a" >&2
    return 1
  fi
  return 0
}

agent_apply_limits() {
  # Best-effort; some shells/sandboxes may ignore ulimit.
  ulimit -v "$(( AGENT_MAX_AS_MB * 1024 ))" 2>/dev/null || true
}

agent_args_target_one_file() {
  # Require at least one path that looks like a single test module.
  local arg
  for arg in "$@"; do
    case "$arg" in
      -*) continue ;;
      *test*.py|tests/*|test_*) return 0 ;;
    esac
  done
  return 1
}

agent_args_request_integration() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      *integration*|*-m\ integration*|*-m=integration*)
        return 0
        ;;
    esac
  done
  return 1
}

agent_refuse_unless_allowed() {
  if agent_args_request_integration; then
    if [[ "${AGENT_ALLOW_INTEGRATION:-}" != "1" ]]; then
      echo "agent-resource-guard: REFUSE — integration tests blocked." >&2
      echo "Set AGENT_ALLOW_INTEGRATION=1 only when the user explicitly asked." >&2
      return 1
    fi
    return 0
  fi
  if agent_args_target_one_file "$@"; then
    return 0
  fi
  if [[ "${AGENT_ALLOW_FULL_SUITE:-}" == "1" ]]; then
    echo "agent-resource-guard: WARN — full suite allowed by AGENT_ALLOW_FULL_SUITE=1." >&2
    return 0
  fi
  echo "agent-resource-guard: REFUSE — pass one test file path (e.g. tests/foo/test_bar.py)." >&2
  echo "Full-suite pytest is blocked unless the user explicitly requested it." >&2
  return 1
}

agent_run_with_timeout() {
  local limit="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    exec timeout --signal=TERM --kill-after=10s "${limit}s" "$@"
  fi
  exec "$@"
}
