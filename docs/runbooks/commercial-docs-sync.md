# Syncing commercial docs to docs.boundarylogic.io

The public site hosts a **read-only mirror** of customer-facing commercial
documentation under `/commercial/`. Source of truth remains the private
`privaci-commercial` repo (`docs/publishable.txt`).

## Workflows

| Workflow | Repo | Trigger |
| --- | --- | --- |
| `publish-commercial-docs.yml` | `privaci-commercial` | Push to `main` on publishable paths |
| `sync-commercial-docs.yml` | `privaci` | `repository_dispatch`, daily cron, manual |
| `docs-pages.yml` | `privaci` | Push to `main` under `docs/**` |

## Secrets

| Secret | Repo | Scope |
| --- | --- | --- |
| `PRIVACI_DOCS_SYNC_TOKEN` | `privaci-commercial` | Dispatch + write to `privaci` |
| `COMMERCIAL_REPO_READ_TOKEN` | `privaci` | Read `privaci-commercial` in sync job |

## Local sync

```bash
python scripts/sync_commercial_docs.py --source ../privaci-commercial
mkdocs build --strict
```

See the commercial runbook:
`privaci-commercial/docs/runbooks/commercial-docs-publish.md`.
