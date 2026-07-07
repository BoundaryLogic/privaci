## Context

SQL Server follows MySQL in the multi-dialect roadmap. ODBC adds container and auth
complexity; connector logic still belongs in the public engine with capability-gated
features for advanced auth modes.

## Goals / Non-Goals

**Goals:**

- Same-engine SQL Server via `aioodbc` + ODBC Driver 18.
- SQL login auth with `sqlserver_connector` capability.
- Entra ID / managed-identity auth with `sqlserver_entra_auth` capability.
- Reuse MySQL connector patterns: catalog, stream, ddl, preflight.

**Non-goals:**

- Cross-engine runs.
- Bulk copy (`bcp`) v1.
- FK subsetting v1.

## Decisions

| Decision | Choice |
| --- | --- |
| Scope | Same-engine SQL Server only |
| Driver | `aioodbc` + ODBC Driver 18 |
| DSN | `mssql://`, `sqlserver://` |
| Sequencing | After `add-mysql-source-target` |
| ODBC in image | Commercial Dockerfile; documented for OSS self-build |

## Architecture

```text
src/privaci/connectors/sqlserver/
  catalog.py    # INFORMATION_SCHEMA + sys.*
  stream.py     # keyset fetch + batch insert
  types.py      # T-SQL type mapping
  auth.py       # SQL login vs Entra token
  ddl.py        # CREATE TABLE replication
```

## Risks / Trade-offs

- **[Risk] ODBC in CI** → Integration tests nightly/manual; unit tests with mocks required.
- **[Risk] Image size** → ODBC layer documented in commercial release notes only.
