# catalog

PostgreSQL schema introspection: tables, columns, primary keys, foreign keys,
partitions, views, and implied (soft) FK heuristics. Builds the dependency
graph used for topological load ordering.

## Public API

| Symbol | Role |
|--------|------|
| `introspect.load_catalog` | Fetch a `CatalogSnapshot` from the source DB |
| `graph.topological_order` | FK-safe table load order |
| `snapshot.CatalogSnapshot` | Immutable catalog model |

## Configuration

`implied_fk_ignore` in `mask-rules.yaml` silences soft-FK warnings for named
columns.

## Example

```bash
privaci catalog inspect --source "$SOURCE_DB_URL"
```
