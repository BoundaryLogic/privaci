# Change: Add PII catalog import from DB comments

## Why

Operators often annotate sensitivity in PostgreSQL column comments. PrivaCI
needs a portable `pii-catalog.yaml` sidecar for declared PII coverage. A
plugin package will validate and drift-check that sidecar later; the public
engine ships the **bootstrap import** so operators can generate a starting
catalog from `pg_description` without a plugin package installed.

## What Changes

- **`pii-catalog.yaml` schema** — versioned models + JSON Schema (parse-only in
  the public engine).
- **`privaci catalog import-db-comments`** — read column comments from a
  PostgreSQL source; emit YAML to stdout or `--output`.
- **Comment → sensitivity heuristics** — documented prefix mapping (e.g.
  `PII:` → `pii_direct`); no row values ever written.
- **Docs** — `docs/pii-catalog.md` + CHANGELOG.

## Non-goals (this change)

- `catalog validate`, drift findings, or license capability gates (plugin
  package follow-up).
- MySQL / SQL Server comment import.

## Capabilities

### New Capabilities

- `pii-catalog-import`: public sidecar models + `import-db-comments` CLI.

## Impact

- Public engine only. Plugin validate/drift remains a separate change.
