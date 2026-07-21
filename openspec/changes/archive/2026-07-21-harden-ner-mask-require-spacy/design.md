## Context

SpaCy NER is an optional extra (`privaci[nlp]`). Historically
`mask_entities_in_text` returned the input unchanged when the model could not
load, so operators without the NLP extra still "succeeded." Auto-detect maps
free-text name patterns to `ner_mask`, amplifying the footgun.

## Goals / Non-Goals

**Goals**

- Fail closed whenever any effective column action is `ner_mask` and SpaCy is
  unavailable, before masked data is written.
- Clear remediation: install `privaci[nlp]` (and `en_core_web_sm`) or change the
  action.
- Keep SpaCy optional for configs that never use `ner_mask`.

**Non-Goals**

- Making SpaCy a hard core dependency of every install.
- Capability-token gating of NER.
- Changing auto-detect pattern → action mapping (notes still map to `ner_mask`).
- Recursive ReDoS AST rewrite (tracked separately).

## Decisions

1. **Probe:** `spacy_available() -> bool` wraps existing `_load_model()` success
   (import + `en_core_web_sm` load). Cache via existing `_MODEL` sentinel.
2. **Explicit YAML:** `validate_ner_mask_actions(config)` at config load (same
   seam as keyed actions) → `ConfigError` exit **3** listing
   `tables.<t>.columns.<c>` paths.
3. **Auto-detect path:** After `build_detection`, preflight
   `verify_ner_mask_spacy(config, detection)` walks effective columns via
   `resolve_effective_table_config` → `PreflightError` exit **2**.
4. **Runtime:** `mask_entities_in_text` raises `MaskingError` exit **1** when
   the model is unavailable (never return raw text for non-empty input).
5. **Empty string:** Still returns unchanged (nothing to mask).
6. **Public language:** Remediation cites `privaci[nlp]` / docs — no product
   tier names (ADR-0007).

## Risks / Trade-offs

- Operators who relied on silent passthrough will see new failures — intentional.
- `privaci plan` / preview with defer_strict still must not write; preflight for
  run/dry-run enforces the gate. Config load catches explicit YAML even without DB.

## Migration Plan

Document in CHANGELOG as breaking behaviour for `ner_mask` without NLP extra.
No config schema version bump.

## Open Questions

None — fail-closed is mandatory for a privacy tool.
