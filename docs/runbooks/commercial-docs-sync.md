# Syncing commercial docs to docs.boundarylogic.io

Customer-facing commercial documentation lives in the private
`privaci-commercial` repo (`docs/publishable.txt`). The public site serves it
under `/commercial/` **without committing copies** into the public engine repo —
content is pulled at **build time** only.

## Workflows

| Workflow | Repo | Trigger |
| --- | --- | --- |
| `publish-commercial-docs.yml` | `privaci-commercial` | Push to `main` on publishable paths |
| `docs-pages.yml` | `privaci` | Push to `main`, `repository_dispatch`, daily cron, manual |

## Secrets

| Secret | Repo | Scope |
| --- | --- | --- |
| `PRIVACI_DOCS_REBUILD_TOKEN` | `privaci-commercial` | Trigger `docs-pages` rebuild on `privaci` (Actions only — **no** git write) |
| `COMMERCIAL_REPO_READ_TOKEN` | `privaci` | Read `privaci-commercial` during docs build |

## Publish flow

```text
privaci-commercial main (publishable doc change)
  → publish-commercial-docs.yml (guard + repository_dispatch)
  → privaci docs-pages.yml (checkout commercial → sync → mkdocs build → deploy)
```

Daily fallback: `docs-pages.yml` cron rebuilds with latest commercial `main`.

## Local preview

With a sibling clone:

```bash
python scripts/sync_commercial_docs.py --source ../privaci-commercial
make docs-serve
```

Or use the production build script (sync + strict build):

```bash
COMMERCIAL_DOCS_SOURCE=../privaci-commercial ./scripts/docs_build.sh
```

Cloudflare Pages: set `COMMERCIAL_REPO_READ_TOKEN` and use
`pip install -e ".[dev]" && ./scripts/docs_build.sh` as the build command.

See the commercial runbook:
`privaci-commercial/docs/runbooks/commercial-docs-publish.md`.
