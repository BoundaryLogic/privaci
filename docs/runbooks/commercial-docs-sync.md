# Syncing commercial docs to docs.boundarylogic.io

Customer-facing commercial documentation lives in the private commercial repo
(`docs/publishable.txt`). The public site serves it under `/commercial/` **without
committing copies** into the public engine repo — content is pulled at **build
time** on Cloudflare Pages.

## Verified production host

| Check | Result |
| --- | --- |
| `docs.boundarylogic.io` | **Cloudflare Pages** (`server: cloudflare`) |
| Source repo | `BoundaryLogic/privaci`, branch `main` |
| Operator doc | `boundarylogic-web/docs/deploying-cloudflare-pages.md` |
| GitHub Pages | Optional mirror at `boundarylogic.github.io/privaci/` — **not** the custom domain |

Cloudflare rebuilds on **push to `privaci` main** (engine doc changes). Commercial
doc changes do **not** push to `privaci`; they POST a **deploy hook** instead.

## Workflows

| Workflow | Repo | Trigger |
| --- | --- | --- |
| `publish-commercial-docs.yml` | commercial | Push to `main` on publishable paths |
| `cloudflare-docs-rebuild.yml` | `privaci` | Daily cron, manual (fallback) |
| `docs-pages.yml` | `privaci` | Push to `main` (GitHub Pages mirror only) |

## Cloudflare Pages settings (docs project)

| Setting | Value |
| --- | --- |
| Build command | `pip install -e ".[dev]" && ./scripts/docs_build.sh` |
| Build output | `site` |
| Env: `PYTHON_VERSION` | `3.12` |
| Env: `COMMERCIAL_REPO_READ_TOKEN` | Read token for private commercial repo |

Create the deploy hook under Cloudflare → Pages → docs project → **Settings →
Builds → Deploy hooks**. Store the hook URL as:

| Secret | Repo |
| --- | --- |
| `CLOUDFLARE_DOCS_DEPLOY_HOOK_URL` | commercial (immediate publish) |
| `CLOUDFLARE_DOCS_DEPLOY_HOOK_URL` | `privaci` (cron fallback) |
| `COMMERCIAL_REPO_READ_TOKEN` | Cloudflare env + `privaci` GHA (build-time checkout) |

## Publish flow

```text
commercial main (publishable doc change)
  → publish-commercial-docs.yml (guard + POST deploy hook)
  → Cloudflare rebuilds privaci main
      → docs_build.sh clones commercial → sync → mkdocs → deploy
```

No commit and no GitHub Actions run is required on `privaci` for commercial-only
doc changes.

Daily fallback: `privaci` `cloudflare-docs-rebuild.yml` cron POSTs the same hook.

## Local preview

```bash
COMMERCIAL_DOCS_SOURCE=../privaci-commercial ./scripts/docs_build.sh
make docs-serve   # or python -m http.server --directory site
```

See the commercial runbook:
`privaci-commercial/docs/runbooks/commercial-docs-publish.md`.
