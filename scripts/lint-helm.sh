#!/usr/bin/env bash
# Lint the PrivaCI Helm chart (helm lint; optional kube-score when installed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="${ROOT}/deploy/helm/privaci"

helm lint "${CHART}"

helm template privaci "${CHART}" > /tmp/privaci-rendered.yaml
echo "Rendered manifest: /tmp/privaci-rendered.yaml"

if command -v kubeconform >/dev/null 2>&1; then
  kubeconform -strict -summary /tmp/privaci-rendered.yaml
elif command -v kubeval >/dev/null 2>&1; then
  kubeval --strict /tmp/privaci-rendered.yaml
else
  echo "kubeconform/kubeval not installed; skipping schema validation"
fi

if command -v kube-score >/dev/null 2>&1; then
  kube-score score /tmp/privaci-rendered.yaml
else
  echo "kube-score not installed; skipping score"
fi
