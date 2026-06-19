## ADDED Requirements

### Requirement: Keyed HMAC hash action (Growth+ tier)

The system SHALL support `action: hmac_hash` as a Level 1 masking action.
The output SHALL equal HMAC-SHA256 over the normalized input value using a
dedicated `pseudonym_key` resolved via `secrets-resolver`. The key SHALL
NOT be the anonymization salt. Default output encoding SHALL be lowercase
hex; config MAY specify `encoding: base64url`.

When no Growth-or-higher license is present, config validation SHALL exit
`5` with remediation pointing to tier licensing documentation.

#### Scenario: Deterministic HMAC output

- **WHEN** a column is configured `action: hmac_hash` and the same value
  is masked twice with the same `pseudonym_key`
- **THEN** the output SHALL be byte-identical both times.

#### Scenario: Different column paths produce different outputs

- **WHEN** the same raw value appears in `users.email` and `contacts.email`
  with `action: hmac_hash` on both
- **THEN** the outputs SHALL differ because the HMAC message includes the
  column path.

#### Scenario: Starter tier rejected

- **WHEN** the license tier is `starter` and a column uses `hmac_hash`
- **THEN** the engine SHALL exit `5` at config validation.

### Requirement: Keyed pseudonym action (Growth+ tier)

The system SHALL support `action: pseudonym` with the same `provider`
parameter as `fake`. The fake value SHALL be selected deterministically
from the provider library using a seed derived from HMAC-SHA256(
`pseudonym_key`, column_path || normalized_input). UNIQUE-constraint
handling SHALL match the salt-based `fake` action.

#### Scenario: Realistic deterministic pseudonym

- **WHEN** `users.email` is configured `action: pseudonym, provider: email`
- **THEN** the output SHALL look like a valid email and SHALL NOT equal the
  original value or the raw HMAC digest.

#### Scenario: FK consistency via seed_alias

- **WHEN** `orders.customer_email` uses `pseudonym` with
  `seed_alias: users.email`
- **THEN** masked values SHALL match the pseudonym produced for the
  referenced user's email column.

### Requirement: Pseudonym key handling

The engine SHALL resolve `pseudonym_key` from `--pseudonym-key`, env
`PSEUDONYM_KEY`, `config.pseudonym_key`, or a secret URI. The resolved
key SHALL be at least 32 bytes. The key SHALL never appear in logs,
errors, or audit payloads.

#### Scenario: Missing pseudonym key

- **WHEN** any column uses `hmac_hash` or `pseudonym` and no key is configured
- **THEN** the engine SHALL exit `4` with a one-line setup hint.

#### Scenario: Key redaction on error

- **WHEN** masking raises an exception while a pseudonym key is in scope
- **THEN** the logged error SHALL NOT contain the key value.
