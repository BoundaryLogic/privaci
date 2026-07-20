## 1. Models & schema

- [x] 1.1 Pydantic models for `pii-catalog.yaml` v1.0
- [x] 1.2 Export JSON Schema under `docs/generated/pii-catalog.schema.json`
- [x] 1.3 Unit tests: parse valid / reject unknown sensitivity

## 2. Import CLI

- [x] 2.1 Query `col_description` for in-scope tables
- [x] 2.2 Map comments → sensitivity (D2 heuristics)
- [x] 2.3 `privaci catalog import-db-comments` → stdout or `--output`
- [x] 2.4 Unit tests with comment rows; PG integration deferred if fixtures down
- [x] 2.5 Public CHANGELOG + docs

## 3. Docs

- [x] 3.1 `docs/pii-catalog.md` + link from `docs/README.md`
- [x] 3.2 CHANGELOG `[Unreleased]`; capability registry entry
