#!/usr/bin/env bash
# Run the PrivaCI evaluation compose stack with whichever container engine is
# available, so contributors don't have to know whether the host uses Docker or
# Podman. Resolution order (override with COMPOSE_CMD):
#   1. docker compose      (only if the Docker daemon is reachable)
#   2. podman compose      (delegates to the Compose v2 plugin when present)
#   3. podman-compose      (the standalone Python implementation, >= 1.0)
#   4. docker-compose      (legacy v1 binary)
#
# Usage:
#   scripts/eval-stack.sh up      # build + run, abort+exit on engine completion
#   scripts/eval-stack.sh down    # stop and remove containers + volumes
#   scripts/eval-stack.sh <args>  # any other compose subcommand, passed through
set -euo pipefail

cd "$(dirname "$0")/.."

resolve_compose_cmd() {
  if [[ -n "${COMPOSE_CMD:-}" ]]; then
    echo "${COMPOSE_CMD}"
    return
  fi
  if command -v docker >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    echo "podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo "ERROR: no usable container compose engine found." >&2
    echo "Install Docker (with a running daemon) or Podman." >&2
    exit 6
  fi
}

COMPOSE="$(resolve_compose_cmd)"
ACTION="${1:-up}"

if [[ "${ACTION}" == "up" && -z "${ANONYMIZATION_SALT:-}" ]]; then
  echo "ERROR: ANONYMIZATION_SALT is not set." >&2
  echo "Run: export ANONYMIZATION_SALT=\"\$(privaci gen-salt)\"" >&2
  exit 4
fi

echo ">> using compose engine: ${COMPOSE}" >&2

case "${ACTION}" in
  up)
    shift || true
    exec ${COMPOSE} up --build --abort-on-container-exit \
      --exit-code-from privaci "$@"
    ;;
  down)
    shift || true
    exec ${COMPOSE} down -v "$@"
    ;;
  *)
    exec ${COMPOSE} "$@"
    ;;
esac
