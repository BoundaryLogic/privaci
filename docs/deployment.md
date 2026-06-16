# Deployment

PrivaCI ships as a container image, a local evaluation `compose.yml` (Docker or
Podman), and a Helm chart for scheduled Kubernetes runs. All artifacts target a
**batch CLI** model: the container runs `privaci run`, streams masked rows, and
exits — it is not a long-lived daemon.

## Container image

| Property | Value |
|----------|-------|
| Base | `python:3.12-slim-bookworm` (digest-pinned on release tags) |
| User | `privaci` (UID/GID **10001**) |
| Entrypoint | `privaci` |
| SpaCy | `en_core_web_sm` baked in at build time |
| Size budget | ≤ 600 MB uncompressed |
| Filesystem | Read-only root compatible; runtime writes only to `/tmp` |

### Build locally

```bash
docker build -t ghcr.io/boundarylogic/privaci:local .
scripts/verify-image.sh ghcr.io/boundarylogic/privaci:local
```

### Run read-only

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e SOURCE_DB_URL=postgresql://... \
  -e TARGET_DB_URL=postgresql://... \
  -e ANONYMIZATION_SALT="$(privaci gen-salt)" \
  -v "$(pwd)/mask-rules.yaml:/config/mask-rules.yaml:ro" \
  ghcr.io/boundarylogic/privaci:local run --config /config/mask-rules.yaml
```

## Evaluation compose (`compose.yml`)

Brings up source Postgres (synthetic seed), empty target Postgres, and the
PrivaCI engine. **Evaluation only** — not for production.

```bash
export ANONYMIZATION_SALT="$(privaci gen-salt)"
make eval-up        # auto-detects Docker or Podman; tear down with: make eval-down
```

`make eval-up` wraps `scripts/eval-stack.sh`, which picks an available compose
engine for you. To drive compose directly instead:

```bash
docker compose up --build        # Docker
podman compose up --build        # Podman (Compose v2 plugin)
podman-compose up --build        # Podman (standalone Python, >= 1.0)
```

- Source seed: `deploy/demo-seed/` (~500 synthetic users, `example.test` emails).
- Config: `examples/mask-rules.demo.yaml` (masks `users`, copies `organizations`
  verbatim so its `NOT NULL` FK referents stay valid).
- Engine runs with `read_only: true` and `tmpfs` on `/tmp`.
- stdout emits JSON-lines events including `run.end` with `status: succeeded`.

For long-running dev databases, use `compose.dev.yml` instead (see
[`local-development.md`](local-development.md)).

### Docker vs Podman

The image, Helm chart, and release workflow are engine-independent. Only the
evaluation compose stack touches the host, and it is verified on both engines.
Windows users run any of these through Docker Desktop or WSL2 — see
[Windows](#windows) below.

| Engine | Command | Notes |
|--------|---------|-------|
| Docker | `docker compose up --build` | Requires a reachable daemon and the user in the `docker` group. |
| Podman (plugin) | `podman compose up --build` | Delegates to the Docker Compose v2 plugin when installed. |
| Podman (Python) | `podman-compose up --build` | Standalone; `>= 1.0` supports `depends_on: condition: service_healthy`. |

Key portability details, all already handled in `compose.yml`:

- **SELinux.** Bind mounts carry the `:z` label, so repo files (config + seed)
  are readable from the container on enforcing hosts (Fedora, RHEL, CentOS
  Stream, Rocky, Alma). `:z` is a no-op on non-SELinux Docker.
- **Rootless Podman.** The engine runs as UID 10001 with a read-only root and a
  `/tmp` tmpfs, which maps cleanly through Podman's user namespace.
- **`docker.sock` permission denied** is a host setup issue, not a PrivaCI one:
  add your user to the `docker` group (`sudo usermod -aG docker $USER`, then
  re-login) or use Podman. `scripts/eval-stack.sh` falls back to Podman
  automatically when the Docker daemon is unreachable.

The verification script accepts either engine via `CONTAINER_ENGINE`:

```bash
CONTAINER_ENGINE=podman scripts/verify-image.sh ghcr.io/boundarylogic/privaci:local
```

### Windows

PrivaCI is a Linux container, so on Windows it runs through a Linux backend.
**Docker Desktop with the WSL2 backend** is the recommended setup; plain WSL2
(Ubuntu) gives the same experience as a native Linux host. The image, the
pre-built GHCR container, and the Helm chart all work unchanged — only the
shell-based convenience wrappers differ.

| Approach | Works | How |
|----------|-------|-----|
| **WSL2 (recommended)** | Yes | Run all Linux commands as-is, including `make eval-up` and `scripts/eval-stack.sh`. |
| **Docker Desktop + PowerShell** | Yes | Use `docker compose` directly; `make` and the `.sh` helpers need Git Bash or WSL. |
| **Helm / Kubernetes** | Yes | `helm install` is OS-independent. |
| **Native Windows (no Linux backend)** | No | The Linux image cannot run without WSL2 or a VM — this is standard for Docker on Windows. |

From PowerShell with Docker Desktop running, set the salt with PowerShell syntax
(not `export`) and drive compose directly:

```powershell
$env:ANONYMIZATION_SALT = "$(privaci gen-salt)"   # or paste a 64-hex-char value
docker compose up --build
```

The `:z` SELinux labels on the bind mounts are ignored by Docker Desktop, just
as they are on macOS, so the same `compose.yml` works without edits.

## Helm chart

Chart path: `deploy/helm/privaci/`

```bash
# Lint locally (helm required)
scripts/lint-helm.sh

# Install — credentials live in existing Secrets, never inline
helm install vp deploy/helm/privaci \
  --set secrets.sourceDbUrlSecret=my-source-creds \
  --set secrets.targetDbUrlSecret=my-target-creds \
  --set secrets.saltSecret=my-salt
```

### Defaults

| Resource | Purpose |
|----------|---------|
| `CronJob` | Scheduled masking run (`schedule` in `values.yaml`) |
| `ConfigMap` | `mask-rules.yaml` |
| `Secret` refs | `SOURCE_DB_URL`, `TARGET_DB_URL`, `ANONYMIZATION_SALT` |
| `securityContext` | `runAsNonRoot`, `readOnlyRootFilesystem`, dropped caps |

Override `values.yaml` for image tag, resources, affinity, tolerations, and
`extraEnv` hooks for the commercial layer.

## Release channels

PrivaCI publishes two channels (ADR-0007). The commercial layer pins the engine
by `CONTRACT_VERSION` (`privaci --contract-version`, currently `1.0`) and
promotes only after its integration suite passes against a **stable** engine
release.

| Channel | Git tag | GitHub release | Container tags | Audience |
|---------|---------|----------------|----------------|----------|
| **Beta** | `vX.Y.Z-beta.N` | Pre-release | `:X.Y.Z-beta.N`, `:beta`, `:edge` | Early adopters, CI smoke on `main` |
| **Stable** | `vX.Y.Z` | Latest release | `:X.Y.Z`, `:X.Y`, `:latest` | Production and Marketplace image builds |

Rules:

- Never build the official Marketplace image from `main` or a beta tag — stable
  tags only.
- Beta tags are cut from `main` for fast iteration; stable tags follow after
  beta soak and full gate green.
- OCI images carry `org.opencontainers.image.version` and
  `io.boundarylogic.contract_version` labels for machine pinning.

### Pin a consumer to a release

```bash
# Contract ABI (commercial layer compatibility)
privaci --contract-version

# Image by channel
docker pull ghcr.io/boundarylogic/privaci:0.1.0-beta.1   # exact beta
docker pull ghcr.io/boundarylogic/privaci:beta             # rolling beta head
docker pull ghcr.io/boundarylogic/privaci:1.0.0          # exact stable (future)
docker pull ghcr.io/boundarylogic/privaci:latest         # stable head only
```

## Release publishing

Tag pushes (`v*`) trigger
[`.github/workflows/release.yml`](https://github.com/BoundaryLogic/privaci/blob/main/.github/workflows/release.yml):

- Contract-version and pack-key guards before build
- Multi-arch image (`linux/amd64`, `linux/arm64`) → `ghcr.io/boundarylogic/privaci`
- Channel-aware tags (see table above)
- SPDX SBOM via `syft`
- Image signing via `cosign` (keyless OIDC where available)
- Helm chart packaged to `oci://ghcr.io/boundarylogic/charts`
- GitHub Release (pre-release for beta tags)

### GHCR publish credentials

The BoundaryLogic org rejects `GITHUB_TOKEN` package writes (`permission_denied:
write_package`) even when the container package lists this repository under
**Manage Actions access**. The release workflow therefore authenticates to GHCR
with a classic personal access token stored as a repository secret.

1. As a GitHub user with **write** access to org packages, create a **classic
   PAT** with scopes `write:packages` and `read:packages`.
2. In this repo: **Settings → Secrets and variables → Actions → New repository
   secret** → name `GHCR_TOKEN`, paste the PAT.
3. If the PAT owner is not the user who pushes release tags, also add
   `GHCR_USERNAME` (the PAT owner's GitHub login).

Re-run the failed **Release** workflow job after adding the secret.

### Cut a beta release

```bash
# 1. Ensure CHANGELOG [Unreleased] is current and gates are green.
# 2. Provision pack signing keys (one-time per rotation):
python scripts/generate_pack_signing_key.py
#    Store PRIVATE_KEY_HEX in GitHub Actions secrets (PACK_SIGNING_PRIVATE_KEY).
#    Publish PUBLIC_KEY_HEX in the release notes; operators set PRIVACI_PACK_PUBLIC_KEY.

git tag -a v0.1.0-beta.1 -m "v0.1.0-beta.1"
git push origin v0.1.0-beta.1
```

See also [pack-signing runbook](runbooks/pack-signing.md) and
[git-history privacy runbook](runbooks/git-history-privacy.md).
