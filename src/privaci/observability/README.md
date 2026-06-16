# observability

Structured JSON-lines logging on stdout, lifecycle events, PII redaction, and
optional Prometheus metrics. Every run moment emits one JSON object per line.

## Public API

| Symbol | Role |
|--------|------|
| `jsonlog.configure_logging` | Install the JSON formatter |
| `events.emit` | Emit a typed lifecycle event |
| `redact.redact_value` | Truncate sensitive strings for logs |
| `metrics.start_metrics_server` | Lazy Prometheus HTTP endpoint |

## Configuration

`--log-level` / `PRIVACI_LOG_LEVEL` and `--prometheus-port`. See
[`docs/observability.md`](../../../docs/observability.md).

## Example

```bash
privaci run --log-level debug --prometheus-port 9090
```
