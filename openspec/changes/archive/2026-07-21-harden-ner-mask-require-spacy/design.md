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

1. **Probe:** `spacy_available() -> bool` is a cheap import /
   `spacy.util.is_package("en_core_web_sm")` check (no full model load). Full
   `spacy.load` stays lazy in `_load_model()`, with negative cache on
   `ImportError`/`OSError` via `_LOAD_FAILED` so config + preflight do not
   retry a failed load. Availability after failure/success is derived from
   `_LOAD_FAILED` / `_MODEL` (no separate probe cache global).
2. **Explicit YAML:** `validate_ner_mask_actions(config)` at config load (same
   seam as keyed actions) → `ConfigError` exit **3** listing
   `tables.<t>.columns.<c>` paths.
3. **Auto-detect path:** After `build_detection`, preflight
   `verify_ner_mask_spacy(config, catalog, detection)` walks effective columns
   via `resolve_effective_table_config` (partition children via
   `config_table_id`) → `PreflightError` exit **2**.
4. **Runtime:** `mask_entities_in_text` raises `MaskingError` exit **1** when
   the model is unavailable (never return raw text for non-empty input).
5. **Empty string:** Still returns unchanged (nothing to mask).
6. **Public language:** Remediation cites `privaci[nlp]` / docs — no product
   tier names (ADR-0007).
7. **`privaci plan`:** Warns (stderr) when effective `ner_mask` lacks SpaCy;
   hard fail remains run/dry-run preflight.

## Risks / Trade-offs

- Operators who relied on silent passthrough will see new failures — intentional.
- `privaci plan` warns on effective `ner_mask` without SpaCy; run/dry-run
  preflight hard-fails (exit 2). Config load catches explicit YAML even without DB.
- Lightweight probe can theoretically pass when a later `spacy.load` fails;
  runtime still fail-closes with exit **1**.

## Migration Plan

Document in CHANGELOG as breaking behaviour for `ner_mask` without NLP extra.
No config schema version bump.

## Open Questions

None — fail-closed is mandatory for a privacy tool.
