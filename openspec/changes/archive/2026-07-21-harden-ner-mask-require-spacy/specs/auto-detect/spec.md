## ADDED Requirements

### Requirement: Effective `ner_mask` requires SpaCy at preflight

After auto-detect merges into effective column actions, preflight SHALL fail
with exit **2** when any effective action is `ner_mask` and SpaCy is
unavailable, naming affected columns and remediating install of `privaci[nlp]`
or an explicit non-NER action.

#### Scenario: Auto-detect ner_mask without SpaCy

- **WHEN** detection assigns `ner_mask` to a notes-like column and SpaCy is
  unavailable
- **THEN** preflight SHALL exit **2** before any target write
