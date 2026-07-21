## Context

Commercial OpenSpec `add-pii-annotation-catalog` splits import (public) from
validate/drift (commercial). This change implements the public half only.

## Decisions

### D1. Sidecar schema (v1.0)

```yaml
version: "1.0"
catalog:
  - table: public.users
    columns:
      - name: email
        sensitivity: pii_direct
        owner: null
        source: pg_comment
        notes: "PII: login email"
```

Sensitivity enum: `pii_direct` | `pii_indirect` | `internal` | `public`.

### D2. Import heuristics

| Comment (case-insensitive prefix) | sensitivity |
| --- | --- |
| `pii:` / `pii_direct:` / `direct:` | `pii_direct` |
| `pii_indirect:` / `indirect:` | `pii_indirect` |
| `internal:` | `internal` |
| `public:` | `public` |
| any other non-empty comment | `pii_indirect` (conservative) |

Empty/whitespace comments are omitted. Table-level comments alone do not create
column entries (v1).

### D3. No PII values

Import writes table/column names, sensitivity, `source: pg_comment`, and the
comment text as `notes`. It never SELECTs row data.

### D4. Placement

Models under `privaci.pii_catalog` (not `config.catalog` — avoid clash with
schema introspection package `privaci.catalog`). CLI under existing
`privaci catalog` Typer group.

### D5. Resume / capability

Import is read-only, no run state, no license capability.

## Non-goals

Validate CLI, drift, commercial tier gates.
