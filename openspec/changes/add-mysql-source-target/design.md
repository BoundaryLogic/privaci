## Context

PostgreSQL support lives entirely in the public engine. MySQL was originally sketched
in the commercial repo; moving it public keeps dialect parity with the ELv2 engine and
lets community contributors test catalog/streaming without a private checkout.

Tier enforcement uses the established capability-token pattern (`keyed_actions` model)
rather than tier-name strings in engine code.

## Goals / Non-Goals

**Goals:**

- Same-engine MySQL/MariaDB source and target via `aiomysql`.
- Reuse masking pipeline, preflight, resume, and audit via `StateBackend` /
  `CatalogBackend`.
- Parameterized SQL only; identifier quoting analogous to PostgreSQL safety rules.
- `mysql_connector` capability gate (exit **5** when absent).

**Non-goals:**

- Cross-engine runs.
- FK subsetting on MySQL v1.
- `json_mask` on MySQL `JSON` columns v1.

## Decisions

| Decision | Choice |
| --- | --- |
| Scope | Same-engine MySQL→MySQL (incl. MariaDB-compatible) |
| Driver | `aiomysql` (async), pinned in `requirements.txt` |
| Location | `src/privaci/connectors/mysql/` |
| Prerequisite | `add-state-schema-abstraction` |
| Gate | `mysql_connector` capability token |

## Architecture

```text
src/privaci/connectors/mysql/
  catalog.py     # information_schema introspection
  stream.py      # keyset SELECT / batch INSERT
  types.py       # MySQL ↔ masking type mapping
  ddl.py         # target schema replication
  dsn.py         # mysql:// / mariadb:// parsing

src/privaci/pipeline/runner.py
  → selects CatalogBackend + StateBackend from DSN scheme
```

## Sequencing

1. Merge `add-state-schema-abstraction`.
2. Ship MySQL connector in public engine.
3. Plugin package grants `mysql_connector` on compliance entitlement.

## Risks / Trade-offs

- **[Risk] JSON path masking gap** → Config validation rejects `json_mask` on MySQL
  JSON with exit **3** and dialect limitation message.
- **[Risk] MyISAM without FK metadata** → WARN and independent load order.
