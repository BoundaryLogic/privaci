# PII catalog sidecar

**Audience:** operators bootstrapping a declared-PII map from PostgreSQL comments.
**When done:** you can generate a git-reviewable `pii-catalog.yaml` and (with a
plugin package later) validate it against mask rules and live schema.

## What it is

`pii-catalog.yaml` lists tables/columns with a sensitivity class and optional
owner/notes. It never stores cell values.

Plugin **validate** / drift checks are a follow-up. This page covers the
**public** bootstrap:

```bash
privaci catalog import-db-comments --output /config/pii-catalog.yaml
```

## Schema (v1.0)

```yaml
version: "1.0"
catalog:
  - table: public.users
    columns:
      - name: email
        sensitivity: pii_direct   # pii_direct | pii_indirect | internal | public
        source: pg_comment        # pg_comment | manual | import
        notes: "PII: login email"
        owner: null
```

JSON Schema: [`docs/generated/pii-catalog.schema.json`](generated/pii-catalog.schema.json).

## Comment → sensitivity heuristics

| Comment prefix (case-insensitive) | sensitivity |
| --- | --- |
| `PII:` / `pii_direct:` / `direct:` | `pii_direct` |
| `pii_indirect:` / `indirect:` | `pii_indirect` |
| `internal:` | `internal` |
| `public:` | `public` |
| any other non-empty comment | `pii_indirect` |

Columns without comments are omitted. Empty sources emit `catalog: []`.

## Security

Import only reads `col_description` metadata. It does not `SELECT` application
tables. Review `notes` before committing — comments themselves must not contain
live PII values.

## Related

- [configuration.md](configuration.md) — mask rules
- Follow-up (plugin package): `catalog validate` + drift
