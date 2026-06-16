# pipeline

End-to-end masking orchestration: pre-flight, schema replication, topological
table streaming, checkpointing, and run finalization.

## Public API

| Symbol | Role |
|--------|------|
| `runner.run_masking_pipeline` | Main async entry for a masking run |
| `runner.PipelineSummary` | Run outcome (tables, rows, duration) |

## Configuration

Driven entirely by `mask-rules.yaml` and CLI flags (`--dry-run`,
`--no-audit-table`).

## Example

```python
import asyncio
from privaci.pipeline import run_masking_pipeline

asyncio.run(run_masking_pipeline(...))
```

The CLI (`privaci run`) is the supported operator interface.
