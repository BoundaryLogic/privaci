## MODIFIED Requirements

### Requirement: Tiered object replication in replicate mode

In `replicate` mode, non-table objects SHALL be handled in tiers across
**pre-data** and **post-data** phases (see capability `ddl-phases`):

1. **Pre-data (structural):** PRIMARY KEY / UNIQUE indexes and foreign keys
   (with tables/schemas/sequences as today).
2. **Post-data default-on:** functions/procedures, then plain views (dependency
   order), excluding elevated objects without an explicit disposition; triggers
   when `replicate_triggers` is true (default).
3. **Post-data opt-in definition-only:** materialized views (`CREATE … WITH NO DATA`;
   never copy stored bytes; optional `REFRESH` after shells).
4. **Post-data opt-in indexes:** non-unique indexes when `replicate_all_indexes: true`.
5. **Skipped:** rules, publications, and triggers when `replicate_triggers: false` —
   `skipped_object` audit with reason.

DDL application order SHALL be:

**pre-data:** schemas → (DEFAULT/CHECK-required functions) → tables → PK/UNIQUE
indexes → foreign keys →  
**(data):** stream rows + per-table `setval` →  
**post-data:** non-unique indexes (if enabled) → remaining functions → views →
materialized view definitions → triggers (if enabled) → optional matview refresh.

#### Scenario: Plain view replicated by default in post-data

- **WHEN** `schema_mode: replicate` and the source defines a non-elevated view
  `active_clinics_v`
- **THEN** the engine SHALL create the view on the target in **post-data** after
  its dependencies
- **AND** SHALL emit `created_object` with `payload.kind = view` and
  `ddl_phase = post-data`.

#### Scenario: Materialized view definition only in post-data

- **WHEN** `replicate_materialized_views: true` and the source defines
  `tickets_open_mv`
- **THEN** the engine SHALL create the materialized view with `WITH NO DATA` in
  **post-data**
- **AND** SHALL NOT copy stored rows from the source materialized view
- **AND** SHALL emit `definition_only_object` with `payload.contents_copied = false`.

#### Scenario: Trigger replicated in post-data by default

- **WHEN** the source has a `BEFORE INSERT` trigger and `replicate_triggers` is
  true (default)
- **THEN** the engine SHALL create the trigger on the target in **post-data**
- **AND** SHALL emit `created_object` with `payload.kind = trigger`.

#### Scenario: Trigger skipped when disabled

- **WHEN** `replicate_triggers: false` and the source has a trigger
- **THEN** the engine SHALL NOT create the trigger
- **AND** SHALL emit `skipped_object` with `payload.kind = trigger` and a
  documented `reason`.
