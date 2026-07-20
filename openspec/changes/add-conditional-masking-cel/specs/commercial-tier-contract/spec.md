## ADDED Requirements

### Requirement: Conditional masking gated by capability membership

Validation of optional `when` CEL guards SHALL enable conditional masking only
when the token `conditional_masking` is present in `LicenseStatus.capabilities`.
It SHALL NOT decide access by matching `LicenseStatus.tier` against hard-coded
name strings.

#### Scenario: Conditional masking allowed by capability

- **WHEN** a config uses a non-empty `when` on any column action, the validator
  grants `conditional_masking`, and CEL compiles
- **THEN** validation SHALL succeed past the capability gate.

#### Scenario: Conditional masking rejected without capability

- **WHEN** a config uses a non-empty `when` and `conditional_masking` is not in
  `LicenseStatus.capabilities`
- **THEN** the engine SHALL exit `5`.

#### Scenario: No `when` ignores capability

- **WHEN** no column action defines `when`
- **THEN** capability state SHALL NOT affect validation for this feature.
