## ADDED Requirements

### Requirement: `StateBackend` and `CatalogBackend` ABCs

The public engine SHALL expose stable ABCs:

- `StateBackend` — target-side run state, checkpoints, audit persistence.
- `CatalogBackend` — source-side schema introspection and dependency graph.

Both SHALL live in `privaci.contracts`, be importable in community mode, and
be versioned with `CONTRACT_VERSION`. Additive methods SHALL bump the minor
contract version.

#### Scenario: ABC import in community mode

- **WHEN** no commercial or dialect plugins are installed
- **THEN** `from privaci.contracts import StateBackend, CatalogBackend`
  SHALL succeed.

#### Scenario: Contract version minor bump

- **WHEN** these ABCs ship
- **THEN** `CONTRACT_VERSION` SHALL increment minor (e.g., `1.0` → `1.1`)
  and the OCI label `io.boundarylogic.contract_version` SHALL match.

### Requirement: Backend discovery via entry points

The system SHALL discover backend implementations via `privaci.plugins`
entry points:

- `state_backend.postgres` (built-in, public engine)
- `catalog_backend.postgres` (built-in, public engine)

Future dialect backends MAY register additional names; the engine SHALL
select exactly one state and one catalog backend per run based on the
source/target DSN scheme.

#### Scenario: Built-in Postgres registration

- **WHEN** the public engine is installed
- **THEN** entry points for Postgres state and catalog backends SHALL be
  present without the commercial layer.

#### Scenario: Unknown dialect

- **WHEN** the target DSN scheme is not supported by any registered
  `state_backend.*` entry point
- **THEN** pre-flight SHALL exit `2` naming the unsupported scheme and
  pointing to documentation.

### Requirement: Commercial layer compatibility

The commercial layer SHALL continue to function when pinned to an engine
whose `CONTRACT_VERSION` major matches. A minor bump for backend ABCs SHALL
NOT require commercial code changes unless the commercial package opts into
custom backend plugins.

#### Scenario: Existing license validator unchanged

- **WHEN** the commercial plugin is installed against engine contract `1.1`
- **THEN** `LicenseValidator` and `UsageMeter` behavior SHALL be unchanged
  from contract `1.0`.
