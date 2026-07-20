## MODIFIED Requirements

### Requirement: Top-level options

The top-level config SHALL accept:

- `version` (required, string)
- `global_salt` (optional string or secret URI; resolved via
  `secrets-resolver`)
- `schema_mode`: `replicate` (default) | `assume_existing`
- `passthrough_copy`: `auto` (default) | `require_binary` | `batch`
- `on_existing_data`: `fail` (default) | `truncate` | `drop_create` |
  `append` (`append` SHALL fail validation in MVP).
- `replicate_views`: bool (default `true`; only in `replicate` mode)
- `replicate_functions`: bool (default `true`; only in `replicate` mode)
- `replicate_triggers`: bool (default `true`; only in `replicate` mode;
  when true, triggers are created in the **post-data** phase)
- `elevated_objects`: mapping of schema-qualified object name → `replicate` | `skip`
  (default empty; only meaningful in `replicate` mode when views/functions are enabled)
- `replicate_materialized_views`: bool (default `false`)
- `refresh_materialized_views`: bool (default `false`)
- `strict_autodetect`: bool (default `false`).
- `replicate_all_indexes`: bool (default `false`; non-unique indexes created in
  **post-data** when true).
- `batch_size`: int (default `10000`).
- `audit_log`: bool (default `true`).
- `auto_detect`: bool (default `true`).
- `tables`: mapping of table identifier → table config.

#### Scenario: `append` strategy in MVP

- **WHEN** `on_existing_data: append` is set
- **THEN** the engine SHALL exit `3` with the message "append strategy
  is not supported in this version. Use truncate or drop_create."

#### Scenario: assume_existing with truncate

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: truncate`
- **THEN** preflight SHALL truncate in-scope target tables and SHALL NOT emit DDL
  for tables, views, or functions.

#### Scenario: assume_existing fail allows empty prebuilt tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and in-scope
  target tables exist and are empty
- **THEN** preflight SHALL succeed without refusing the run solely for emptiness.

#### Scenario: assume_existing fail refuses populated tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and any in-scope
  target table contains at least one row
- **THEN** preflight SHALL exit `2`.

#### Scenario: assume_existing rejects drop_create

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: drop_create`
- **THEN** config validation SHALL exit `3`.

#### Scenario: replicate_triggers default is true

- **WHEN** `replicate_triggers` is omitted from config
- **THEN** the engine SHALL treat it as `true` in `schema_mode: replicate`.
