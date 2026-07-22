#!/usr/bin/env bash
# Critical mutation suite (mask + config). Never run from default ci-local.
# Requires: pip install -e '.[dev]' (cosmic-ray).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! python -c "import cosmic_ray" 2>/dev/null; then
  echo "mutation-critical: cosmic-ray not installed (pip install -e '.[dev]')" >&2
  exit 1
fi

run_slice() {
  local module_path="$1"
  local test_path="$2"
  local label="$3"
  local session config
  session="${TMPDIR:-/tmp}/privaci-cosmic-ray-${label}-$$.sqlite"
  config="${TMPDIR:-/tmp}/privaci-cosmic-ray-${label}-$$.toml"
  cleanup_slice() { rm -f "$session" "$config"; }
  trap cleanup_slice RETURN

  cat >"$config" <<EOF
[cosmic-ray]
module-path = "${module_path}"
timeout = 30.0
excluded-modules = []
test-command = "python -m pytest ${test_path} -q --tb=no -x"

[cosmic-ray.distributor]
name = "local"
EOF

  echo "mutation-critical: initializing session (${label})…"
  cosmic-ray init "$config" "$session"
  echo "mutation-critical: executing (${label})…"
  cosmic-ray exec "$config" "$session"
  cosmic-ray report "$session" || true
}

run_slice "src/privaci/mask" "tests/mask" "mask"
run_slice "src/privaci/config" "tests/config" "config"
echo "mutation-critical: done (warn-only until kill-score calibrated — see docs/ci-gates.md)"
