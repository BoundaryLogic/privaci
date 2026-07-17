## ADDED Requirements

### Requirement: run --force-restart
The `privaci run` command SHALL accept `--force-restart` to abandon an
incomplete target run and start fresh when `on_existing_data` is `truncate` or
`drop_create`. With `on_existing_data: fail`, `--force-restart` SHALL be
rejected at preflight (exit **2**).

#### Scenario: Help documents the flag
- **WHEN** an operator runs `privaci run --help`
- **THEN** `--force-restart` is listed with collision-policy requirements

#### Scenario: fail policy refuses force restart
- **WHEN** `--force-restart` is combined with `on_existing_data: fail`
- **THEN** the command exits **2** before starting a run

### Requirement: Plugin-contract CLI wording
CLI help for contract/version surfaces SHALL use plugin-contract language, not
banned product-tier phrasing (ADR-0007).

#### Scenario: contract-version help
- **WHEN** help text for `--contract-version` (or equivalent) is shown
- **THEN** it refers to the plugin contract ABI version without product-tier
  names
