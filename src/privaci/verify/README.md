# verify

Post-run value-free audit: compares row counts, schema fingerprints, and
sampled column statistics between source and target without logging PII.

## Public API

| Symbol | Role |
|--------|------|
| `compare.run_verification` | Execute all verification checks |
| `models.VerificationReport` | Structured pass/fail summary |

## Configuration

`--sample-size` on `privaci verify` (default 1000 rows per table).

## Example

```bash
privaci verify --config mask-rules.yaml --sample-size 500
```
