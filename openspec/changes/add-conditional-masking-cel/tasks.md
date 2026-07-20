## 1. CEL sandbox module

- [x] 1.0 Spike: pin candidate `cel-python` version; confirm compile/eval API,
      sandbox restrictions, and deadline behaviour (document in design if
      switching libraries)
- [x] 1.1 Add chosen package to `requirements.in`; lock with pip-compile
- [x] 1.2 Implement `privaci.cel` — build typed activation from `ColumnInfo` + row dict (D9 map)
- [x] 1.3 Implement compile helper with size/depth limits and 5 ms deadline wrapper
- [x] 1.4 Unit tests: allowed ops, rejected builtins, timeout, non-bool → error

## 2. Config layer

- [x] 2.1 Add optional `when: str` to all column action models
- [x] 2.2 Config-load: capability gate + syntax/size compile (no catalog)
- [x] 2.3 Preflight / validate-with-catalog: type-check; exit `3` with YAML path;
      unsupported PG types (D9) fail closed
- [x] 2.4 Wire `conditional_masking` capability gate (exit `5`; no tier-name matching)

## 3. Masking pipeline + eligibility

- [x] 3.1 Cache compiled CEL on `MaskingEngine` construction
- [x] 3.2 Evaluate `when` before action dispatch; passthrough when false;
      suppress auto-detect for that cell
- [x] 3.3 Emit rollup `column.conditional_skip` (counts + expression hash only)
- [x] 3.4 Mark tables with any `when` binary-COPY ineligible; `require_binary` → exit `2`

## 5. Tests & docs

- [x] 5.1 Integration test: mask only rows where `status == 'closed'`
- [x] 5.2 Negative tests: syntax error, unknown field, unsupported type,
      missing capability → exit `5`, `require_binary` + `when` → exit `2`
- [x] 5.3 Update `docs/configuration.md`, `docs/state-schema.md`,
      `CHANGELOG.md` (ADR-0007 public language); JSON Schema via model field
- [x] 5.4 Register capability tests in `scripts/capability_test/registry.py`
      and matrix cells in `scripts/capability_test/matrix.py`

## Deferred (commercial train)

- [ ] 4.2 Commercial repo: grant `conditional_masking` for `standard` and
      `compliance` in `capabilities_for_tier`; update licensing docs

