#!/usr/bin/env bash
# Production docs build: generate reference pages, sync commercial docs, mkdocs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

python scripts/generate_docs.py

COMMERCIAL_SOURCE="${COMMERCIAL_DOCS_SOURCE:-}"
if [[ -z "${COMMERCIAL_SOURCE}" && -d "${ROOT}/../privaci-commercial" ]]; then
  COMMERCIAL_SOURCE="${ROOT}/../privaci-commercial"
fi

if [[ -n "${COMMERCIAL_SOURCE}" ]]; then
  python scripts/sync_commercial_docs.py --source "${COMMERCIAL_SOURCE}"
elif [[ -n "${COMMERCIAL_REPO_READ_TOKEN:-}" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' EXIT
  git clone --depth 1 \
    "https://x-access-token:${COMMERCIAL_REPO_READ_TOKEN}@github.com/BoundaryLogic/privaci-commercial.git" \
    "${tmp}/privaci-commercial"
  python scripts/sync_commercial_docs.py --source "${tmp}/privaci-commercial"
else
  cat >&2 <<'EOF'
ERROR: Commercial docs are generated at build time from privaci-commercial.

Set one of:
  COMMERCIAL_DOCS_SOURCE=/path/to/privaci-commercial   (local or CI checkout)
  COMMERCIAL_REPO_READ_TOKEN=<token>                   (clone at build time)

Local default: sibling ../privaci-commercial when present.
EOF
  exit 1
fi

mkdocs build --strict

printf '%s\n' \
  'User-agent: *' \
  'Allow: /' \
  'Sitemap: https://docs.boundarylogic.io/sitemap.xml' \
  > site/robots.txt
