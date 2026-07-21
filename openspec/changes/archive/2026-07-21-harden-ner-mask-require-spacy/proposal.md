## Why

`ner_mask` currently fail-opens when SpaCy is not installed: the engine returns
source text unchanged at DEBUG and still reports success. Auto-detect assigns
`ner_mask` to notes/comments/bio-style columns, so a base install can copy raw
PII into the target. Missing capability must hard-fail before any write.

## What Changes

- **BREAKING (behaviour):** `ner_mask` without SpaCy/`en_core_web_sm` fails at
  config validate (explicit YAML) and at preflight (including auto-detect
  merges). Runtime no longer passthroughs.
- Add `spacy_available()` probe and shared column enumeration helpers.
- Document prerequisites and exit codes; CHANGELOG under Unreleased.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `masking-pipeline`: NER requires SpaCy; no silent passthrough when unavailable.
- `config-yaml`: Explicit `ner_mask` rejected at load when SpaCy unavailable.
- `auto-detect`: Effective `ner_mask` from detection must fail preflight without SpaCy.

## Impact

- `src/privaci/mask/ner.py`, config loader validation, preflight checks
- Docs: `configuration.md`, `error-codes.md`, CHANGELOG
- Tests: `tests/mask/test_ner.py` plus config/preflight unit tests
- Optional extra remains `privaci[nlp]`; SpaCy stays optional for installs that
  never use `ner_mask`
