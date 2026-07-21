## ADDED Requirements

### Requirement: Explicit `ner_mask` requires SpaCy at config load

When any column action in `mask-rules.yaml` is `ner_mask`, config validation
SHALL verify that SpaCy and the `en_core_web_sm` model can be loaded. When
unavailable, validation SHALL fail with exit **3** naming each
`tables.<t>.columns.<c>` path and remediating with `pip install 'privaci[nlp]'`
(and model install) or changing the action.

#### Scenario: Explicit ner_mask without SpaCy

- **WHEN** config sets `action: ner_mask` on any column and SpaCy is unavailable
- **THEN** the engine SHALL exit **3** before connecting to databases for a run

#### Scenario: No ner_mask ignores SpaCy

- **WHEN** no column uses `ner_mask`
- **THEN** SpaCy availability SHALL NOT affect config validation
