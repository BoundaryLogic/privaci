## ADDED Requirements

### Requirement: Dockerfile

The system SHALL ship a `Dockerfile` building an image with these
properties:

- Base image: `python:3.12-slim` pinned to a specific digest in the
  release tag.
- Non-root user named `privaci`, UID/GID 10001.
- All Python deps installed via `pip install --no-cache-dir -r
  requirements.txt` from a pre-`pip-compile`d lockfile.
- SpaCy model `en_core_web_sm` downloaded at image build time, not
  runtime.
- `ENTRYPOINT ["privaci"]` so the image is a CLI tool, not a daemon.
- No ports exposed (`EXPOSE` lines absent for the default image).
- Read-only root filesystem compatible — the engine writes nothing to
  the filesystem outside `/tmp` (which is mounted `tmpfs` by default).

#### Scenario: Image runs as non-root

- **WHEN** the image is run with `docker run --user 0 privaci:latest`
- **THEN** the engine SHALL still operate; **WHEN** run without
  `--user` override
- **THEN** the running process SHALL have UID 10001.

#### Scenario: SpaCy model is bundled

- **WHEN** the image runs offline (no internet access)
- **THEN** SpaCy NER SHALL still function (model is baked in).

#### Scenario: Image runs read-only

- **WHEN** the image is run with `docker run --read-only`
- **THEN** the engine SHALL function correctly with no filesystem
  writes outside `/tmp`.

### Requirement: docker-compose.yml for local evaluation

The system SHALL ship a `docker-compose.yml` that brings up:

- A source PostgreSQL with a sample seed dataset (~1 MB synthetic
  data) so users can try `privaci` in under 60 seconds.
- A target PostgreSQL (empty).
- The privaci container wired to both, with a minimal
  `mask-rules.yaml`.

The compose stub SHALL be intended for evaluation only and SHALL be
documented as such.

#### Scenario: First-time evaluation

- **WHEN** a new user runs `docker compose up`
- **THEN** within 60 seconds the engine SHALL stream from source to
  target, mask the seed data, and emit `run.end` with `status:
  succeeded`.

### Requirement: Helm chart for Kubernetes production

The system SHALL ship a Helm chart `boundarylogic/privaci` with:

- A `CronJob` resource (default schedule overridable via values).
- `Secret` references for source DB URL, target DB URL, and salt; no
  inline secret material.
- A `ConfigMap` for `mask-rules.yaml`.
- `securityContext` enforcing `runAsNonRoot: true`, `readOnlyRootFilesystem:
  true`, dropped capabilities, `allowPrivilegeEscalation: false`.
- A documented `values.yaml` covering image tag, schedule, resources,
  affinity, tolerations, and override hooks for the commercial layer.

#### Scenario: Helm install with secrets in Kubernetes secrets

- **WHEN** the user runs `helm install vp boundarylogic/privaci
  --set-string secrets.sourceDbUrlSecret=my-prod-db-creds` (referencing
  an existing K8s secret)
- **THEN** the rendered manifests SHALL mount the secret as env vars
  with no inline credentials.

#### Scenario: Chart passes `kubeval`

- **WHEN** the chart is rendered with default values
- **THEN** the output SHALL pass `kubeval` and `kube-score` linting.

### Requirement: Image and chart publishing

Release CI SHALL publish:

- Multi-arch (`linux/amd64`, `linux/arm64`) container image tags:
  `boundarylogic/privaci:<version>`, `boundarylogic/privaci:latest` (latest
  stable only).
- Helm chart packaged and pushed to the chart repository
  (`charts.boundarylogic.io` or equivalent OCI registry).

#### Scenario: Multi-arch image

- **WHEN** the image is pulled on `linux/arm64` and `linux/amd64`
- **THEN** both SHALL pull the correct arch via manifest list.

#### Scenario: SBOM and signature

- **WHEN** an image is published
- **THEN** an SPDX SBOM SHALL be attached and the image SHALL be signed
  via `cosign`.

### Requirement: Image size budget

The published image SHALL be ≤ 600 MB uncompressed for the public
community edition.

#### Scenario: Image size budget

- **WHEN** `docker image inspect boundarylogic/privaci:<version>`
  reports `Size`
- **THEN** the value SHALL be ≤ 600,000,000 bytes (600 MB).
