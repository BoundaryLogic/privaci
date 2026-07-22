#!/usr/bin/env bash
# Duplicate-code gate (constitution Article VIII).
# Scans critical packages; fails if duplicated lines >= threshold in .jscpd.json.
#
# Requires Node.js + npx (jscpd is run via npx; no repo npm dependency).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx not found — install Node.js 20+ to run the duplicate-code gate." >&2
  echo "  See docs/ci-gates.md (duplicate code)." >&2
  exit 1
fi

# Pin jscpd for reproducible CI/local runs.
JSCPD_VERSION="${JSCPD_VERSION:-4.0.5}"

PATHS=(
  src/privaci/mask
  src/privaci/config
  src/privaci/secrets
  src/privaci/stream
)

echo "check-duplicates: jscpd@${JSCPD_VERSION} on ${PATHS[*]}"
npx --yes "jscpd@${JSCPD_VERSION}" \
  --config .jscpd.json \
  "${PATHS[@]}"
