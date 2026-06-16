#!/usr/bin/env bash
# Verify a built PrivaCI image meets deployment-artifacts constraints.
# Usage: scripts/verify-image.sh [image_ref]
# Container engine is configurable via CONTAINER_ENGINE (default: docker).
set -euo pipefail

IMAGE="${1:-ghcr.io/boundarylogic/privaci:local}"
ENGINE="${CONTAINER_ENGINE:-docker}"
MAX_BYTES=600000000

SIZE="$("${ENGINE}" image inspect "${IMAGE}" --format '{{.Size}}')"
echo "Image ${IMAGE} size: ${SIZE} bytes"

if [[ "${SIZE}" -gt "${MAX_BYTES}" ]]; then
  echo "FAIL: image exceeds 600 MB budget (${MAX_BYTES} bytes)" >&2
  exit 1
fi

echo "Checking non-root default user..."
"${ENGINE}" run --rm --entrypoint id "${IMAGE}" -u | grep -qx '10001'

echo "Checking read-only root filesystem..."
"${ENGINE}" run --rm --read-only --tmpfs /tmp "${IMAGE}" --help >/dev/null

echo "Checking bundled SpaCy model (offline NER import)..."
"${ENGINE}" run --rm --entrypoint python "${IMAGE}" \
  -c "import spacy; spacy.load('en_core_web_sm'); print('spacy ok')"

echo "PASS: ${IMAGE}"
