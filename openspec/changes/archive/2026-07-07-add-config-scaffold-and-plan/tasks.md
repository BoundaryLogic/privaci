# Tasks: add-config-scaffold-and-plan

## 1. `privaci init`

- [x] 1.1 Add `src/privaci/cli/_init.py` — orchestrate catalog + autodetect → Config model
- [x] 1.2 Map autodetect findings to column actions (high confidence → YAML; medium → summary warning)
- [x] 1.3 Serialize to valid mask-rules YAML (`version: "1.0"`, env salt ref, sensible defaults)
- [x] 1.4 Wire `privaci init` in `app.py` with `--source`, `--output`, `--schema`, `--force`
- [x] 1.5 Refuse overwrite without `--force`; exit **2** on connection/config errors
- [x] 1.6 Add generator header comment (review before production)

## 2. `privaci plan`

- [x] 2.1 Add `src/privaci/cli/_plan.py` — source-only preflight path (no target connect)
- [x] 2.2 Reuse `build_detection` + effective table config; row estimates from source stats where cheap
- [x] 2.3 Human output (enhance dry-run column summary style)
- [x] 2.4 `--format json` structured plan for CI
- [x] 2.5 Wire `privaci plan` in `app.py`

## 3. Shared / refactor

- [x] 3.1 Extract shared “detection → display lines” from `_run.py` if needed (avoid duplication)
- [x] 3.2 Ensure init/plan never log PII values from source data

## 4. Tests

- [x] 4.1 `tests/cli/test_init_plan.py` — generated YAML validates via `load_config`; high-confidence columns present
- [x] 4.2 `tests/cli/test_init_plan.py` — plan runs without TARGET_DB_URL; JSON + text format
- [x] 4.3 Negative: init without source → exit 2; init existing file without `--force` → exit 2
- [x] 4.4 `tests/config/test_scaffold.py` — scaffold + export unit tests

## 5. Documentation

- [x] 5.1 Update `docs/quickstart.md` — init → plan → dry-run → run happy path
- [x] 5.2 Update `docs/cli-reference.md` + `docs/generated/cli-reference.md` + `docs/configuration.md`
- [x] 5.3 CHANGELOG v1.1.0 entry
- [x] 5.4 Note in public README quickstart one-liner

## 6. Cross-repo follow-up (after public release)

- [ ] 6.1 Link deployment docs to public init/plan quickstart (private plugin repo)
- [ ] 6.2 Bump plugin repo engine pin on v1.1.0 tag
