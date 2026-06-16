# config

Loads and validates `mask-rules.yaml` via strict pydantic models. Rejects
unknown keys and exports the JSON Schema used by `privaci schema config`.

## Public API

| Symbol | Role |
|--------|------|
| `loader.load_config` | Parse and validate a config file path |
| `loader.export_json_schema` | Emit the mask-rules JSON Schema |
| `loader.migrate_config` | Version migration helper |
| `models.Config` | Root document model |
| `models.TableConfig` | Per-table strategy and column rules |

## Configuration

See [`docs/configuration.md`](../../../docs/configuration.md) and the
auto-generated
[`docs/generated/configuration-reference.md`](../../../docs/generated/configuration-reference.md).

## Example

```python
from privaci.config import load_config

cfg = load_config("mask-rules.yaml")
```
