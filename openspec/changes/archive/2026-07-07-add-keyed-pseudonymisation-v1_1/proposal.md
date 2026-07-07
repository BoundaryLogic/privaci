## Why

The MVP `hash` action (SHA-256 of salt || value) is one-way and unsuitable when
downstream teams need stable, joinable tokens across systems without storing a
lookup table. Regulated customers also ask for keyed pseudonymisation that
survives salt rotation policy changes and supports cross-environment analytics
with a dedicated HMAC key separate from the anonymization salt.

AES-FF1 format-preserving encryption is the long-term answer for preserving
string shape (e.g., 9-digit SSN layout), but it adds crypto surface area,
key-management UX, and audit complexity. Growth-tier customers need keyed
deterministic pseudonyms now; FF1 can follow in a later change.

## What Changes

- **New L1 actions (Growth+ tier):**
  - `hmac_hash` — HMAC-SHA256 over the normalized column value using a
    dedicated key resolved via `secrets-resolver` (`PSEUDONYM_KEY` or
    `config.pseudonym_key` URI). Output is base64url or hex per config.
  - `pseudonym` — keyed deterministic Faker: same HMAC seed derivation as
    `hmac_hash`, but selects a realistic fake from the provider library
    instead of emitting the digest. Preserves referential integrity when
    combined with `seed_alias`.
- **Key resolution:** `pseudonym_key` is required when any column uses
  `hmac_hash` or `pseudonym`. Minimum 32 bytes after resolution; validated at
  boot. Distinct from `ANONYMIZATION_SALT`.
- **Tier gating:** Without a Growth-or-higher license (or community mode
  override in dev), config validation rejects these actions with exit `5` and
  a tier-upgrade message.
- **Explicit non-delivery:** AES-FF1 / format-preserving encryption is
  deferred; documented in design as a future Enterprise candidate.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `masking-pipeline`: Adds `hmac_hash` and `pseudonym` to the L1 action
  catalog; keyed seed derivation; tier gate for Growth+.

## Impact

- **Code:** `src/privaci/mask/` (new action handlers), `src/privaci/config/actions.py`
  (discriminated union), `src/privaci/mask/faker/` (keyed seed path).
- **Contracts:** `LicenseValidator` tier check wired at config validation
  (Growth+ for keyed actions).
- **Dependencies:** none new (stdlib `hmac` + existing faker stack).
- **Docs:** `docs/configuration.md` (action reference), `CHANGELOG.md`,
  `.env.example` (`PSEUDONYM_KEY`).
- **Tests:** 100% coverage on new masking paths; property tests for
  determinism and cross-column isolation.
- **Security:** HMAC key never logged; output is non-reversible without the key.
