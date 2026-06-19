## 1. CEL sandbox module

- [ ] 1.1 Add `cel-python` to `requirements.in`; lock with pip-compile
- [ ] 1.2 Implement `privaci.cel.env` — build typed activation from `ColumnInfo` + row dict
- [ ] 1.3 Implement compile helper with size/depth limits and 5 ms eval timeout wrapper
- [ ] 1.4 Unit tests: allowed ops, rejected builtins, timeout enforcement

## 2. Config layer

- [ ] 2.1 Add optional `when: str` to all column action models
- [ ] 2.2 Compile `when` expressions at validation when catalog snapshot is wired
- [ ] 2.3 Type-check CEL against column types; exit `3` with YAML path on failure
- [ ] 2.4 Wire Growth+ tier gate when any `when` is non-empty

## 3. Masking pipeline

- [ ] 3.1 Cache compiled CEL on `MaskingEngine` construction
- [ ] 3.2 Evaluate `when` before action dispatch; passthrough when false
- [ ] 3.3 Emit `conditional_skip` audit events (expression hash only)

## 4. Tests & docs

- [ ] 4.1 Integration test: mask only rows where `deleted == false`
- [ ] 4.2 Negative tests: syntax error, unknown field, starter tier
- [ ] 4.3 Update `docs/configuration.md`, JSON Schema export, `CHANGELOG.md`
