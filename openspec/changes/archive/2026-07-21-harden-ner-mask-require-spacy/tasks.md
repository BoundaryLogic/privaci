## 1. Probe and runtime fail-closed

- [x] 1.1 Add `spacy_available()` in `mask/ner.py`
- [x] 1.2 Raise `MaskingError` when model unavailable for non-empty `ner_mask` text
- [x] 1.3 Unit tests: fail when unavailable; empty string unchanged; mock available OK

## 2. Config and preflight gates

- [x] 2.1 `validate_ner_mask_actions` at config load (exit 3) for explicit YAML
- [x] 2.2 `verify_ner_mask_spacy` in preflight after detection (exit 2)
- [x] 2.3 Unit tests for both gates (mock `spacy_available`)

## 3. Docs and registry

- [x] 3.1 Update `docs/configuration.md` and `docs/error-codes.md`
- [x] 3.2 CHANGELOG `[Unreleased]`; capability registry if needed
- [x] 3.3 Sync OpenSpec deltas into main specs when archiving (or with this PR)
