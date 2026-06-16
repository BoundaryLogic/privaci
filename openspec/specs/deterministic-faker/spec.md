# deterministic-faker Specification

## Purpose
TBD - created by archiving change init-privaci-engine. Update Purpose after archive.
## Requirements
### Requirement: Salt + hash deterministic fake generation

The system SHALL produce deterministic fake values from real values
using a salted hash:

```
seed   = sha256(salt || column_path || normalized_input).digest()[:16]
index  = int.from_bytes(seed, 'big') % len(fake_library)
fake   = fake_library[index]
```

Where `column_path` is `<schema>.<table>.<column>` and
`normalized_input` is the unicode-normalized (NFC), case-preserved
string form of the input.

#### Scenario: Same input + same salt → same output

- **WHEN** the faker is invoked twice with identical inputs and salt
- **THEN** the output SHALL be byte-identical.

#### Scenario: Different salts → different outputs

- **WHEN** two salts differ in any byte
- **THEN** the outputs for the same input SHALL almost certainly differ
  (the probability of accidental collision SHALL be negligible).

#### Scenario: Different column paths → different fakes for same input

- **WHEN** `users.email` and `customers.email` both contain
  `john@acme.com`
- **THEN** the two faked outputs SHALL differ, preventing trivial
  cross-table correlation.

### Requirement: FK consistency for referencing columns

The system SHALL preserve FK consistency by using the **referenced
column's path** for hashing when masking an FK column. This ensures
that `orders.customer_email` (FK to `users.email`) produces the same
fake as `users.email` for the same input.

#### Scenario: FK column resolves to referenced column's faker path

- **WHEN** `orders.customer_email` is a FK to `users.email` and the
  catalog records the FK
- **THEN** the faker SHALL hash with `column_path = "users.email"` for
  `orders.customer_email`.

#### Scenario: No FK declared

- **WHEN** two columns share values but have no declared FK between
  them
- **THEN** the engine SHALL not infer a relationship; outputs SHALL
  differ unless `seed_alias` is configured manually.

#### Scenario: User-declared FK alias

- **WHEN** the config sets `tables.orders.customer_email.seed_alias:
  "users.email"`
- **THEN** the engine SHALL hash with the aliased path, even without a
  catalog FK.

### Requirement: UNIQUE-constraint-aware strategy switching

The system SHALL detect when a column is part of a UNIQUE constraint or
UNIQUE index (recorded by `postgres-catalog`) and SHALL switch to a
collision-resistant strategy for that column:

```
fake_value = base_fake + uniqueness_suffix(seed)
```

Where `uniqueness_suffix` produces a stable hex token from the seed,
long enough that birthday collisions stay negligible across realistic
table sizes. The token SHALL be at least 16 hex characters (64 bits): at
1M distinct inputs the collision probability is ~3e-8, satisfying the
1M-row scenario below. The suffix SHALL be appended in a way that
respects the column type:

- For email: `john.doe@fake.tld` → `john.doe+a1b2c3d4e5f60718@fake.tld`.
- For arbitrary text: `<base>__a1b2c3d4e5f60718`.
- For numeric IDs: deterministic remap to a non-colliding integer space
  preserving width.

#### Scenario: UNIQUE email column with 1M rows

- **WHEN** a UNIQUE email column is masked across 1M distinct inputs
- **THEN** the output SHALL contain 1M distinct masked emails (no
  collisions).

#### Scenario: Non-UNIQUE name column

- **WHEN** a non-UNIQUE `first_name` column is masked across 100k
  distinct inputs
- **THEN** outputs MAY repeat (consistent with k-anonymity).

#### Scenario: Composite UNIQUE constraint

- **WHEN** the catalog declares `UNIQUE(first_name, last_name)`
- **THEN** the engine SHALL apply uniqueness suffixing to whichever
  column the masking strategy targets such that the composite remains
  unique.

### Requirement: Built-in fake providers

The system SHALL ship the following providers:

- `first_name`, `last_name`, `full_name`
- `email` (configurable fake-domain list, default: `fakedom.net`,
  `example.test`, `tryvault.dev`)
- `phone` (E.164 normalized; preserves country-code where detectable)
- `address`, `street`, `city`, `postcode`, `country`
- `dob` (ISO-8601 date; preserves age bracket ±5 years)
- `ip_address` (RFC 5737 test ranges)
- `ssn` (always `XXX-XX-XXXX` with hash-derived digits in `000-99-9999`
  test range)
- `credit_card` (test BINs only, Luhn-valid)
- `uuid` (deterministic UUIDv4 derived from seed)
- `company`, `job_title`
- `username`
- `password` (always a fixed test placeholder `privaci-test-pw`
  per `.cursorrules` — never a real-looking hash)

Each provider SHALL have its own static library and SHALL never emit a
real-looking PII value that could be mistaken for production data.

#### Scenario: Generated SSNs are out of valid issuance ranges

- **WHEN** SSN provider produces 10,000 outputs
- **THEN** all outputs SHALL fall within `000-99-XXXX` (an SSA-reserved
  test range), and SHALL pass a "is-fake-SSN" structural check.

#### Scenario: Generated credit cards pass Luhn

- **WHEN** the credit_card provider produces an output
- **THEN** the output SHALL pass the Luhn checksum and start with a
  documented test BIN.

### Requirement: Custom provider registration (extension point)

The system SHALL expose a registration mechanism allowing the commercial
layer (or, optionally, a user plugin) to register additional providers:

```python
from privaci.contracts import register_provider
```

Custom providers SHALL implement the `FakeProvider` ABC and SHALL be
deterministic (no I/O, no time-based randomness).

#### Scenario: Plugin provider used in config

- **WHEN** a plugin registers a provider named `medical_record_number`
  and the YAML references `provider: medical_record_number`
- **THEN** the engine SHALL load and use the plugin provider.

#### Scenario: Unknown provider referenced

- **WHEN** the YAML references an unregistered provider
- **THEN** the engine SHALL exit `3` at config validation naming the
  missing provider.

