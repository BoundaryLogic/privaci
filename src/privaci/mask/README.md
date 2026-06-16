# mask

Three-tier masking pipeline: L1 column rules (fake, regex, hash), L2 SpaCy
NER, and L3 LLM refinement (commercial). Deterministic fakes use the global
salt; referential fakes support `seed_alias`.

## Public API

| Symbol | Role |
|--------|------|
| `engine.MaskingEngine` | Per-row masking orchestrator |
| `faker.generate_fake` | Deterministic synthetic values |
| `faker.register_provider` | Register a custom `FakeProvider` |
| `ner.apply_ner_mask` | Level-2 entity redaction |

## Configuration

Per-column `action` entries in `mask-rules.yaml`. Providers include
`first_name`, `email`, `phone`, `ner_mask`, `ai_refine`, etc.

## Example

```yaml
columns:
  email: { action: fake, provider: email }
  bio: { action: ner_mask, entities: [PERSON, ORG] }
```
