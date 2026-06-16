# stream

Constant-memory table streaming via PostgreSQL COPY-binary (with text-mode
fallback), batch assembly, and retry logic.

## Public API

| Symbol | Role |
|--------|------|
| `table.stream_table` | Mask and load one table |
| `copy_binary.CopyBinaryStreamer` | Binary COPY encode/decode path |
| `batch.RowBatch` | In-memory batch container |

## Configuration

Global and per-table `batch_size` in `mask-rules.yaml` (default 10_000 rows).

## Example

Streaming is invoked by the pipeline; operators tune throughput with:

```yaml
batch_size: 5000
tables:
  public.events:
    batch_size: 20000
```
