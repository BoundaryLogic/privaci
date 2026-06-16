# state

Run state in the target database `_privaci` schema: runs, per-table
checkpoints, audit log, and resume metadata.

## Public API

| Symbol | Role |
|--------|------|
| `runs.create_run` / `finish_run` | Lifecycle of a masking run |
| `checkpoints.write_checkpoint` | Per-batch PK watermark |
| `resume.find_resumable_run` | Locate interrupted runs |
| `audit.write_audit_rows` | Per-decision audit trail |

## Configuration

`audit_log: false` in config or `--no-audit-table` disables audit writes.
See [`docs/state-schema.md`](../../../docs/state-schema.md).

## Example

```bash
privaci resume --config mask-rules.yaml
```
