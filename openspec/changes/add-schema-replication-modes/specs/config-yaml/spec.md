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
- `elevated_objects`: mapping of schema-qualified object name → `replicate` | `skip`
  (default empty; only meaningful in `replicate` mode when views/functions are enabled)
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

#### Scenario: assume_existing fail allows empty prebuilt tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and in-scope
  target tables exist with zero rows
- **THEN** config and preflight SHALL allow the run to proceed past collision checks.

#### Scenario: assume_existing fail refuses populated in-scope tables

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: fail` and any in-scope
  target table has rows
- **THEN** preflight SHALL exit `2`
- **AND** SHALL NOT treat missing identity/`SERIAL` columns as an exception.

#### Scenario: assume_existing rejects drop_create

- **WHEN** `schema_mode: assume_existing` and `on_existing_data: drop_create`
- **THEN** config validation SHALL exit `3`
- **AND** SHALL explain that customer-managed DDL would not be recreated.

#### Scenario: passthrough_copy default is auto

- **WHEN** `passthrough_copy` is omitted from config
- **THEN** the engine SHALL behave as `passthrough_copy: auto`.

#### Scenario: elevated_objects disposition values

- **WHEN** `elevated_objects` contains an entry whose value is neither `replicate` nor
  `skip`
- **THEN** config validation SHALL exit `3` naming the invalid disposition.
