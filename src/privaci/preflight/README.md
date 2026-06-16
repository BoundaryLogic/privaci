# preflight

Pre-run validation: salt resolution, config/schema checks, target collision
policy, FK strategy validation, and connectivity probes.

## Public API

| Symbol | Role |
|--------|------|
| `runner.run_preflight` | Execute all checks and return structured results |
| `salt.resolve_salt` | Load and fingerprint the anonymization salt |
| `checks.validate_exclude_strategy` | Ensure excluded tables do not orphan FKs |

## Configuration

`on_existing_data`, table `strategy`, and `null_orphan_fks` in
`mask-rules.yaml`. Salt from `ANONYMIZATION_SALT` or `global_salt`.

## Example

```bash
privaci dry-run   # runs preflight without writes
privaci validate  # config-only validation
```
