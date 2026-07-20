---
title: "State & audit schema"
description: "_privaci runs, checkpoints, and audit_log tables written to the target database during masking."
---

# Run state & audit (`_privaci` schema)

PrivaCI records every run's progress and audit trail in a dedicated `_privaci`
schema **in the target database**. This is what makes a crashed run resumable,
gives auditors a SQL-queryable history of PII handling, and records a stable
`source_db_hash` for run identity. The rationale lives in
[ADR-0004](adr/0004-state-in-target-database.md).

The engine creates this schema automatically on first run. You only need to
grant the masking role permission to do so.

## Required grant

The target role must be able to create the schema on first run:

```sql
GRANT CREATE ON DATABASE your_target_db TO masking_role;
```

If the grant is missing, the run stops before writing any data with
[exit code 2](error-codes.md#exit-code-2-pre-flight-failure) and names the
grant in the remediation line.

## Tables

The schema is created idempotently (`CREATE SCHEMA IF NOT EXISTS`,
`CREATE TABLE IF NOT EXISTS`) inside a single transaction, so re-running is
always safe.

| Table | One row per | Purpose |
|-------|-------------|---------|
| `_privaci.runs` | run | Lifecycle status, identity fingerprints, schema snapshot, summary |
| `_privaci.table_checkpoints` | (run, table) | Per-batch resume point: last PK and rows processed |
| `_privaci.audit_log` | masking/detection event | Queryable trail of what was masked and what PII was detected |
| `_privaci.schema_metadata` | database | Records the state-schema version for compatibility checks |

### `_privaci.runs`

Key columns: `run_id` (UUIDv7 PK), `status`
(`in_progress` → `succeeded`/`failed`/`interrupted`), `started_at`,
`ended_at`, `engine_version`, `config_hash`, `salt_fingerprint`,
`source_db_hash`, `source_schema_snapshot` (jsonb), `summary` (jsonb).

Identity fingerprints are non-reversible and **never** contain secrets:

- `salt_fingerprint` = `sha256(salt)[:16]` — never the salt itself.
- `source_db_hash` = `sha256("<host>:<port>/<dbname>")` — credentials excluded.
  The same host+port+database always hashes the same; a different database name
  on the same host hashes differently.
- `config_hash` = `sha256` of the canonicalized config JSON (key-order
  independent).

### `_privaci.table_checkpoints`

Key columns: `(run_id, schema_name, table_name)` PK, `status`
(`pending`/`in_progress`/`done`/`failed`), `last_pk_value`, `rows_processed`,
`last_update_at`. Each batch commit advances `last_pk_value` and adds the
batch's row count to `rows_processed` **within the same transaction as the data
write**, so progress can never run ahead of committed rows.

### `_privaci.audit_log`

Key columns: `audit_id` (UUIDv7 PK), `run_id`, `event_at`, `level`
(`info`/`warning`/`error`), `event_type`, `schema_name`, `table_name`,
`column_name`, `payload` (jsonb). Built-in `event_type` values:

| `event_type` | Meaning |
|--------------|---------|
| `column.masked` | Column action applied |
| `column.passed_through` | Column copied without masking |
| `column.pii_detected` | Detection note for a column |
| `column.conditional_skip` | CEL `when:` skipped masking for some rows (`expression_hash`, counts) |
| `cycle_break` | FK cycle deferred for load |
| `polymorphic_fk_warning` | Polymorphic FK risk |
| `implied_fk_warning` | Implied FK risk |
| `binary_fallback` | Binary COPY unavailable; used batch |
| `strict_mode_violation` | Strict autodetect refusal context |
| `new_table` | Partition child discovered vs prior snapshot |
| `skipped_object` | Object not replicated (`kind` + `reason`) |
| `created_object` | View, function, trigger, or index created on target (`payload.ddl_phase`) |
| `definition_only_object` | Matview shell created without copying source bytes |
| `schema.validated` | `assume_existing` validation passed |
| `schema.validation_failed` | `assume_existing` validation refused |

Commercial layers may add their own `event_type` strings. When
`replicate_materialized_views` is enabled, matview shells emit
`definition_only_object` with `contents_copied: false`; optional refresh sets
`refreshed: true` on that audit row.

## Force-restart and resume

Incomplete runs (`in_progress`, `interrupted`, `failed`) are resumed with
`privaci resume` when identity fingerprints match and, in `schema_mode:
replicate`, a `source_schema_snapshot` is present. Missing snapshots refuse
resume (exit **2**).

`privaci run --force-restart` abandons incomplete runs and starts fresh. It
requires `on_existing_data: truncate` or `drop_create` (not `fail`).

## Disabling the audit log

The audit log is on by default. To skip writing `_privaci.audit_log` (the run
row in `_privaci.runs` is still written, so resumability is unaffected):

```yaml
# mask-rules.yaml
audit_log: false
```

or on the CLI:

```bash
privaci run --no-audit-table ...
```

## Schema version compatibility

`_privaci.schema_metadata.schema_version` records the layout version. If the
schema was initialized by a **newer** engine, the run stops with
[exit code 2](error-codes.md#exit-code-2-pre-flight-failure) and the message
"target was initialized by a newer engine; pin to the matching version or run
migrations." Pin to the matching engine version, or point at a fresh target.

## Querying the audit trail

The state schema is plain PostgreSQL — query it with the SQL you already know:

```sql
-- What did the most recent run mask?
SELECT table_name, column_name, payload->>'action' AS action,
       payload->>'rows_affected' AS rows
FROM _privaci.audit_log
WHERE run_id = (SELECT run_id FROM _privaci.runs
                ORDER BY started_at DESC LIMIT 1)
  AND event_type = 'column.masked'
ORDER BY table_name, column_name;
```

> The `_privaci` schema is owned by PrivaCI. Application code must not read from
> or write to it; the pre-flight target-empty check ignores it.
