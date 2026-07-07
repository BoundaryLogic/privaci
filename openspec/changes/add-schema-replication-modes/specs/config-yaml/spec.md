## MODIFIED Requirements

### Requirement: Top-level options

The top-level config SHALL accept:

- `version` (required, string)
- `global_salt` (optional string or secret URI; resolved via
  `secrets-resolver`)
- `schema_mode`: `replicate` (default) | `assume_existing`
- `on_existing_data`: `fail` (default) | `truncate` | `drop_create` |
  `append` (`append` SHALL fail validation in MVP).
- `replicate_views`: bool (default `true`; only in `replicate` mode)
- `replicate_functions`: bool (default `true`; only in `replicate` mode)
- `replicate_materialized_views`: bool (default `false`)
- `refresh_materialized_views`: bool (default `false`)
- `strict_autodetect`: bool (default `false`).
- `replicate_all_indexes`: bool (default `false`).
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
