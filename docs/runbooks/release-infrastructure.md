---
title: "Runbook: release infrastructure"
description: "Operator notes for PrivaCI release pipelines, artifact promotion, and infra hooks."
---

# Release infrastructure checklist

Use this after creating a **new** `privaci` repository, rotating credentials, or
when release / Pages / PyPI workflows fail with auth errors.

## Repository secrets (Settings → Secrets and variables → Actions)

| Secret | Required for | Notes |
|--------|----------------|-------|
| `GHCR_TOKEN` | **Release** (container + Helm push) | Classic PAT with `write:packages` + `read:packages`. Org GHCR rejects `GITHUB_TOKEN` with `permission_denied: write_package`. |
| `GHCR_USERNAME` | Release (optional) | PAT owner's GitHub login. Defaults to the user who pushed the tag (`github.actor`). Set when PAT owner ≠ tag pusher. |
| `PACK_SIGNING_PRIVATE_KEY` | Future pack-signing in CI | Hex Ed25519 private key from `scripts/generate_pack_signing_key.py`. Not consumed by `release.yml` today; store for when pack publish is wired in. |

`GITHUB_TOKEN` is injected automatically — do not create it. `release.yml`
defaults to `contents: read` and elevates to `contents: write` +
`id-token: write` only on the publish job (GitHub Release + cosign OIDC).
GHCR/Helm push use `GHCR_TOKEN`, not `packages: write` on `GITHUB_TOKEN`.
The publish job also needs `actions: write` for Docker Buildx `type=gha` cache.
`docs-pages.yml` similarly keeps workflow `contents: read` and elevates
`pages: write` + `id-token: write` only on the deploy job.

**Repository secrets, not environment secrets:** `release.yml` does not use a
GitHub Environment. Put `GHCR_TOKEN` under **Repository secrets**.

## GitHub Environments (Settings → Environments)

| Environment | Created by | Secrets needed | Notes |
|-------------|------------|----------------|-------|
| `github-pages` | First Pages deploy | None | `docs-pages.yml` keeps workflow `contents: read`; the **deploy** job elevates `pages: write` + `id-token: write`. Auto-created when Pages is enabled. |
| `testpypi` | First manual PyPI workflow run (or create manually) | None (OIDC) | Configure **Trusted Publishing** on [TestPyPI](https://test.pypi.org/manage/account/publishing/) for workflow `publish-pypi.yml`, environment `testpypi`. |
| `pypi` | Same | None (OIDC) | Configure **Trusted Publishing** on [PyPI](https://pypi.org/manage/account/publishing/) for workflow `publish-pypi.yml`, environment `pypi`. This repo's `pypi` environment may require a reviewer approval before publish. |

Trusted Publisher fields (both indexes):

- **Owner:** `BoundaryLogic`
- **Repository:** `privaci`
- **Workflow:** `publish-pypi.yml`
- **Environment:** `testpypi` or `pypi` (must match the workflow input)

Re-create Trusted Publishers if the repository was deleted and recreated — old
bindings do not transfer.

## Organization settings

| Setting | Location | Value |
|---------|----------|-------|
| Workflow permissions | Org → Settings → Actions → General | **Read and write** (repo can override, but org must not block writes) |
| GHCR package access | `ghcr.io/boundarylogic/privaci` → Package settings → Manage Actions access | Add `BoundaryLogic/privaci` with **Write** (necessary but not sufficient — still need `GHCR_TOKEN`) |
| Helm chart package | `ghcr.io/boundarylogic/charts` (created on first push) | Same Actions access + public visibility after first publish |

## Tag re-runs vs workflow updates

**Re-running an old Release workflow uses the workflow file from the tag commit,**
not `main`. If you fixed `release.yml` on `main` after tagging, re-runs of that
tag will **not** pick up the fix.

Options:

1. **Cut a new tag** (e.g. `v0.1.0-beta.4`) on `main` after secrets and workflow fixes land.
2. **Move the tag** (force-push tag to current `main`) — only if no partial release
   artifacts exist. After `release.yml` idempotent release step lands, a tag
   re-push updates GHCR/Helm and **edits** the existing GitHub Release instead of
   failing with `Release.tag_name already exists`.
3. Add `workflow_dispatch` to `release.yml` (future) to run against a chosen ref.

## After a successful Release workflow

1. **GHCR visibility** — Package settings → Change visibility → **Public** (so
   `docker pull ghcr.io/boundarylogic/privaci:…` works without auth).
2. **Helm OCI chart** — Same for `ghcr.io/boundarylogic/charts` if published.
3. **GitHub Release** — Created automatically at the end of `release.yml` when
   push steps succeed (earlier failures skip this step).
4. **PyPI** — Still manual: Actions → **Publish to PyPI** → choose `testpypi` or
   `pypi` after Trusted Publishing is configured.

## What each workflow needs (quick reference)

| Workflow | Trigger | Secrets / env |
|----------|---------|----------------|
| `ci.yml` | Push / PR to `main` | None |
| `release.yml` | Tag `v*` | `GHCR_TOKEN` (+ optional `GHCR_USERNAME`) |
| `docs-pages.yml` | Push to `main` (docs paths) | Environment `github-pages` (auto) |
| `publish-pypi.yml` | Manual dispatch | Environments `testpypi` / `pypi` + PyPI Trusted Publisher |

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Release.tag_name already exists` on Create GitHub release | Tag was force-pushed after a successful release | Merge idempotent `release.yml` fix, then re-push the tag or re-run the workflow; GHCR images may already be published |
| `403 Forbidden` / `permission_denied: write_package` on GHCR push | Org blocks `GITHUB_TOKEN` package writes | Add `GHCR_TOKEN` PAT; use a **new tag** (not a re-run of an old one) |
| `Missing repository secret GHCR_TOKEN` | Secret not created | Settings → Secrets → `GHCR_TOKEN` |
| Pages 404 | Pages not enabled | Settings → Pages → Source: **GitHub Actions**; or run `docs-pages.yml` once |
| PyPI publish 403 | Trusted Publisher not configured | Re-register on pypi.org / test.pypi.org for this repo |
| Release waits for approval | `pypi` environment has required reviewers | Approve in Actions, or adjust environment protection rules |
