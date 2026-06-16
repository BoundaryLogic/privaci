# Observability

PrivaCI emits a structured, machine-readable event stream so a run can be
piped straight into log aggregation, audited after the fact, or watched live.
Every significant lifecycle moment is one JSON object on its own line on
stdout. stderr is reserved for unexpected, uncaught failures.

For the per-command flags see [`cli-reference.md`](cli-reference.md); for the
on-disk audit trail see [`state-schema.md`](state-schema.md).

## The stdout event stream

Each line is a complete JSON object terminated by `\n`, with no ANSI color
codes or other decoration. That means you can pipe stdout through `jq`:

```bash
privaci run --config mask-rules.yaml | jq -c 'select(.event == "table.end")'
```

Every event carries a common envelope:

| Field | Description |
|-------|-------------|
| `timestamp` | ISO-8601 UTC with microseconds (e.g. `2026-06-10T21:14:09.123456+00:00`). |
| `level` | `debug`, `info`, `warning`, or `error`. |
| `event` | The event identifier (see the catalog below). |
| `run_id` | The run UUID, present from `run.start` onward. |

Event-specific fields are merged into the same object. Ordinary (non-lifecycle)
log lines are rendered as `{"event": "log", "message": "...", ...}`.

### Example

```json
{"timestamp":"2026-06-10T21:14:09.000123+00:00","level":"info","event":"run.start","run_id":"018f...","engine_version":"0.1.0","config_hash":"...","salt_fingerprint":"...","source_db_hash":"...","commercial_layer_present":false}
{"timestamp":"2026-06-10T21:14:09.450000+00:00","level":"info","event":"table.start","schema_name":"public","table_name":"users","estimated_rows":1000}
{"timestamp":"2026-06-10T21:14:11.500000+00:00","level":"info","event":"table.progress","schema_name":"public","table_name":"users","rows_processed":5000,"rows_per_sec":2380.95,"percent_complete":100.0}
{"timestamp":"2026-06-10T21:14:11.900000+00:00","level":"info","event":"table.end","schema_name":"public","table_name":"users","rows_processed":1000,"duration_ms":1450.2,"status":"done"}
{"timestamp":"2026-06-10T21:14:12.000000+00:00","level":"info","event":"run.end","run_id":"018f...","status":"succeeded","duration_ms":3000.0,"tables_processed":1,"rows_processed":1000,"errors":0}
```

## Event catalog

| Event | Level | Key fields |
|-------|-------|------------|
| `run.start` | info | `engine_version`, `config_hash`, `salt_fingerprint`, `source_db_hash`, `commercial_layer_present` |
| `preflight.ok` / `preflight.fail` | info / error | `checks` (array of `{name, status, detail}`) |
| `schema.cloned` | info | `tables_created`, `schemas_created` |
| `table.start` | info | `schema_name`, `table_name`, `estimated_rows` |
| `table.progress` | info | `rows_processed`, `rows_per_sec`, `percent_complete` |
| `table.end` | info | `rows_processed`, `duration_ms`, `status` |
| `column.masked` | info | `schema_name`, `table_name`, `column_name`, `action`, `rows_affected` |
| `cycle_break` | info | `tables`, `deferred_constraint` |
| `polymorphic_fk_warning` | warning | `table_id`, `message` |
| `implied_fk_warning` | warning | `source_column_path`, `message` |
| `skipped_object` | info | `schema_name`, `object_name`, `kind` |
| `new_table` | info | `schema_name`, `table_name`, `reason` |
| `binary_fallback` | warning | `schema_name`, `table_name`, `unsupported_types` |
| `warning` | warning | `message` |
| `error` | error | `message`, `exit_code` |
| `run.end` | info | `status`, `duration_ms`, `tables_processed`, `rows_processed`, `errors` |

### `table.progress` throttling

For long-running tables, `table.progress` is emitted **at most once every two
seconds per table** so the stream stays readable on multi-million-row loads.

## PII redaction

No event payload ever contains a raw column value. Any value-bearing field is
collapsed to a non-reversible marker: `***` followed by at most the first eight
characters of the value (e.g. `john@acme.com` → `***john@acm`). Empty or null
values render as `***`. A captured stdout file is therefore safe to share for
debugging or audit.

## Log level

Control verbosity with `--log-level` or the `PRIVACI_LOG_LEVEL` environment
variable (default `info`):

```bash
privaci run --log-level debug --config mask-rules.yaml
PRIVACI_LOG_LEVEL=warning privaci run --config mask-rules.yaml
```

At `debug`, additional trace events appear; at `warning` or `error`, only the
matching severities are emitted.

## Optional Prometheus metrics

Metrics are **off by default** — no network port is opened unless you ask for
one. Pass `--prometheus-port` to serve the Prometheus exposition format on
`/metrics`:

```bash
privaci run --prometheus-port 9100 --config mask-rules.yaml
# then: curl http://localhost:9100/metrics
```

Exposed series:

| Metric | Type | Labels |
|--------|------|--------|
| `privaci_run_rows_processed_total` | counter | `table` |
| `privaci_run_duration_seconds` | histogram | — |
| `privaci_run_errors_total` | counter | `type` |
| `privaci_table_progress_ratio` | gauge | `table` |

The endpoint requires the optional `prometheus-client` package:

```bash
pip install prometheus-client
```

If the package is missing, `--prometheus-port` exits with a configuration error
(exit code 3) explaining how to install it.
