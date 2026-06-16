# ADR-0005: Require an explicit user-supplied salt with no silent default

## Status

Accepted — 2026-05-28

## Context

The deterministic-faker promise — "same input + same salt = same fake
across runs" — only holds when the salt is stable. A salt that silently
changes between runs (because it was derived from infrastructure that
rotates) silently breaks every downstream test that asserts on a
specific fake value.

We considered three options for salt UX:

1. **Default derived from a stable-ish source** (cluster ID, source DB
   URL hash, MAC address). Convenient on first run; silently broken
   when infrastructure rotates. Rejected.
2. **Auto-generated on first run and persisted to `_privaci`.**
   Customer never sees the salt; if `_privaci` is dropped or the
   target DB rotates, all deterministic fakes change. Rejected.
3. **User-supplied. Fail loudly if missing.** Customer owns the salt
   the same way they own any other secret. Accepted.

## Decision

The engine resolves the salt from (in priority order):

1. `--salt` CLI flag.
2. `ANONYMIZATION_SALT` env var.
3. `config.global_salt` field (literal or secret URI).
4. `(no fallback)` → engine exits `4` with a one-line setup command:
   ```
   privaci gen-salt > .privaci-salt
   chmod 600 .privaci-salt
   export ANONYMIZATION_SALT=$(cat .privaci-salt)
   ```

Minimum length: 32 characters, validated at boot. `privaci gen-salt`
produces a 64-character hex string (256 bits) from `secrets.token_hex(32)`.

The salt is wrapped in a `SecretStr` type that redacts on `__repr__`
and `__str__`. A logging filter scrubs it from log records. Only a
16-byte SHA-256 fingerprint is stored in `_privaci.runs`.

## Consequences

### Customer-facing implications

- **Slightly more friction on first run.** Mitigated by `privaci
  gen-salt` and clear documentation.
- **Customer is responsible for backing up the salt.** Losing it means
  the next run's fakes differ from previous runs' fakes, which may
  break tests. Documentation makes this explicit.
- **Salt rotation has downstream consequences.** Customers who rotate
  the salt invalidate their existing deterministic-fake test
  expectations. Documented as an intentional behavior; the audit log
  records the salt fingerprint per run so it's possible to retroactively
  identify "tests were green up to run X with salt fingerprint Y".

### Why no derived default

- Cluster IDs change with infrastructure refreshes (terraform replace,
  RDS endpoint change, EKS blue/green).
- Source DB URL hashes change when the customer migrates the source.
- Either silent change breaks the deterministic-fake guarantee
  silently. Loud failure is much better than silent inconsistency for
  a security-sensitive tool.

### Implementation requirement

- `privaci gen-salt` writes only to stdout. Documentation uses shell
  redirection so the customer chooses the storage path; the engine
  never assumes a file path.
- The salt fingerprint (sha256(salt)[:16]) is recorded in
  `_privaci.runs.salt_fingerprint` so a future "did the salt change
  between these two runs?" diagnostic is possible without exposing the
  salt.
