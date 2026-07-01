# Data subsetting

**Audience:** DevOps configuring FK-aware staging slices.

**Status:** Integrated in commercial **v1.0.0** with public engine **v1.0.0+**.
`CommercialRunEnhancer` builds row filters from `commercial-extensions.yaml` and the
public streaming pipeline applies them during `privaci run`.

---

## Problem

Full-table copies are too large for tenant-scoped staging. Subsetting copies
only rows reachable via foreign keys from a filtered root table.

## Config (`commercial-extensions.yaml`)

```yaml
version: "1.0"
subset:
  - table: public.accounts
    predicate: "tenant_id = 451"
  - table: public.orders
    predicate: "created_at >= '2024-01-01'"
```

| Field | Description |
| --- | --- |
| `table` | Schema-qualified root table |
| `predicate` | Trusted SQL `WHERE` fragment (no semicolons) |

## Behaviour

1. Evaluate each root predicate on the source database
2. Compute transitive FK closure of primary keys (up to 64 passes)
3. Emit per-table `WHERE` fragments; the engine restricts reads to those rows

Integration path:

- `privaci_commercial.run_enhancer.CommercialRunEnhancer.build_enhancements_async`
  → `build_subset_row_filters`
- Public `privaci.pipeline.streaming` merges `row_filters` into table reads

## Beta limitations

These are known v0.1.x constraints — not bugs in config validation.

| Limitation | Effect |
| --- | --- |
| **Composite root FK pull** | If a table references the root via a **multi-column** FK, values in that FK are **not** pulled into closure. A warning is logged; downstream rows reachable only through that FK may be missing. |
| **Large PK filters** | Up to 256 PKs use inline ``IN (...)`` literals. Larger sets materialize into a **session temp table** on the source connection (same session as streaming reads). Composite PK temp tables use matching column types from the catalog. |
| **Cycles and self-references** | Closure is iterative (max 64 passes), not a single nested SQL tree. Typical org ↔ user cycles work; pathological graphs may stop before full fixpoint. |
| **Single-database PostgreSQL** | No cross-database subsetting |
| **Trusted predicates only** | Predicates are operator-authored SQL — not end-user input |

## Example run

```bash
export COMMERCIAL_EXTENSIONS=/path/to/commercial-extensions.yaml
privaci run --source "$SOURCE_DB_URL" --target "$TARGET_DB_URL" --config mask-rules.yaml
```

With subset entries present, logs include `subset_tables=N` on the commercial enhancer.

## Related

- [JSONB masking](jsonb-masking.md) — often combined with subset slices
- Public [configuration](https://docs.boundarylogic.io/configuration/) — base masking rules
- Public [RunEnhancer hook](https://docs.boundarylogic.io/extending-privaci/) — how row filters attach
