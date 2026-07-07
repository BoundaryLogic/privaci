# commercial-tier-contract Specification

## ADDED Requirements

### Requirement: Capability tokens on `LicenseStatus`

`LicenseStatus` SHALL carry a `capabilities: frozenset[str]` field of opaque capability tokens,
defaulting to an empty set. The public engine SHALL treat these as membership tokens only — it
SHALL NOT interpret, enumerate, or match license-tier name strings to decide feature access.
The field SHALL be additive (default-valued) and SHALL NOT bump `CONTRACT_VERSION`.

The installed `LicenseValidator` is the sole source of capability tokens. Community mode SHALL
grant an empty capability set.

#### Scenario: Additive field defaults to empty

- **WHEN** a `LicenseStatus` is constructed without `capabilities`
- **THEN** `capabilities` SHALL equal `frozenset()`
- **AND** the instance SHALL remain hashable/comparable (frozen dataclass)

#### Scenario: Community mode grants no capabilities

- **WHEN** no license plugin is installed and the community fallback validates
- **THEN** `LicenseStatus.is_valid` SHALL be `True` (the engine may run)
- **AND** `LicenseStatus.capabilities` SHALL be empty

#### Scenario: Older plugin build without the field

- **WHEN** a previously built `LicenseValidator` constructs `LicenseStatus` without
  `capabilities`
- **THEN** validation SHALL still succeed
- **AND** the empty default SHALL apply (fail-closed for capability-gated features)

### Requirement: Keyed actions gated by capability membership

`validate_keyed_actions` SHALL enable keyed masking actions (`hmac_hash`, `pseudonym`) only when
the token `keyed_actions` is present in `LicenseStatus.capabilities`. It SHALL NOT decide access
by matching `LicenseStatus.tier` against hard-coded name strings, and the engine SHALL retain no
tier-name allow-set for this purpose.

#### Scenario: Keyed actions allowed by capability

- **WHEN** a config uses `hmac_hash` or `pseudonym`, the validator grants `keyed_actions`, and a
  `pseudonym_key` is configured
- **THEN** validation SHALL pass

#### Scenario: Keyed actions rejected without capability

- **WHEN** a config uses `hmac_hash` or `pseudonym` and `keyed_actions` is not in
  `capabilities` (including community mode)
- **THEN** the engine SHALL raise a license error and exit **5**, naming the offending columns
- **AND** it SHALL NOT fall through to running the keyed action

#### Scenario: Missing key still gates after capability

- **WHEN** `keyed_actions` is granted but no `pseudonym_key` is configured
- **THEN** the engine SHALL exit **4** for the missing key (unchanged ordering)

#### Scenario: No keyed actions is a no-op

- **WHEN** a config uses no keyed actions
- **THEN** capability state SHALL NOT affect validation and it SHALL pass
