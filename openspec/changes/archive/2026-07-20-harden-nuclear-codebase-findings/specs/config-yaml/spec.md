## ADDED Requirements

### Requirement: Canonical table strategy resolution
Config consumers SHALL resolve per-table strategy and excluded table ids through
a single shared helper (no divergent copies that disagree on
`config_table_id` vs raw identifier).

#### Scenario: Partition child uses config table id
- **WHEN** strategy is resolved for a partition child
- **THEN** the shared helper uses the same config key rules everywhere

### Requirement: null_orphan_fks contract is documented and enforced
`null_orphan_fks` SHALL be documented as requiring skipped FK DDL to excluded
parents plus NULL streaming when the flag is true; contradictory “later phase”
matview wording SHALL be removed from operator docs when matview flags ship.

#### Scenario: Docs match flag behaviour
- **WHEN** an operator reads `docs/configuration.md` for `null_orphan_fks`
- **THEN** the documented behaviour matches runtime skip-FK and optional nulling
  and does not claim matviews are only a future phase while flags exist

