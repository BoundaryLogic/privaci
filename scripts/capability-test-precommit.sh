#!/usr/bin/env bash
# Pre-commit hook: validate registry, then run the quick capability suite.
#
# Runs full quick (public + commercial unit) when ../privaci-commercial exists;
# otherwise public-unit only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/check_capability_registry.py

COMMERCIAL="${ROOT}/../privaci-commercial"
if [[ -d "${COMMERCIAL}" ]]; then
  exec ./scripts/capability-test-suite.sh quick
fi

exec ./scripts/capability-test.sh --cap public-unit
