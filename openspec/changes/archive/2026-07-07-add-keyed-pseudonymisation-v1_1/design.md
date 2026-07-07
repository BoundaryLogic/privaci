## Context

MVP ships `hash` (SHA-256) and salt-based `fake`. Customers on Growth tier need
joinable tokens and keyed pseudonyms without a tracking database. The
commercial layer already exposes `LicenseStatus.tier`; keyed actions are the
first masking features gated above community/starter.

## Goals / Non-Goals

**Goals:**

- Deterministic, keyed outputs: same `(key, column_path, value)` → same output.
- HMAC key resolved via existing secrets URI chain; separate from salt.
- `pseudonym` reuses deterministic-faker providers with HMAC-derived seed.
- Fail fast at config validation when key missing or tier insufficient.

**Non-Goals:**

- AES-FF1 / FF3-1 format-preserving encryption (deferred).
- Reversible tokenization or encrypted lookup tables.
- Per-row random (non-deterministic) pseudonyms.
- Replacing existing `hash` or `fake` semantics.

## Decisions

### D1. HMAC-SHA256 for keyed digest

**Decision:** `hmac_hash` computes `HMAC-SHA256(pseudonym_key, normalize(value))`.
Default encoding: hex lowercase. Optional `encoding: base64url`.

**Alternatives:** HKDF per column (more complex, no customer ask). Plain
SHA-256 with key concatenation (not a proper MAC).

### D2. Shared seed for `pseudonym`

**Decision:** `pseudonym` derives `seed = hmac_digest[:16]` and feeds the
existing faker index selection, with `column_path` in the HMAC message prefix
(same isolation as salt-based fake).

**Rationale:** Reuses provider libraries and UNIQUE-aware suffix logic.

### D3. Key separate from salt

**Decision:** `pseudonym_key` is its own config/env/secret field. Rotating
salt does not rotate HMAC tokens; rotating pseudonym key intentionally
changes all keyed outputs.

### D4. Tier gate at validation

**Decision:** `hmac_hash` and `pseudonym` require tier ∈
`{growth, business, enterprise}`. Starter and community exit `5` at validate
time with remediation pointing to licensing docs.

### D5. Defer AES-FF1

**Decision:** Do not ship FF1 in this change. Document as future Enterprise
candidate requiring NIST SP 800-38G review and dedicated key ceremony UX.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Key leakage via logs | `SecretStr` wrapper; same redaction filter as salt |
| HMAC outputs used as display values | Docs warn `hmac_hash` is not human-readable; steer to `pseudonym` |
| Cross-column correlation if message format wrong | Include `table.column` in HMAC AAD |

## Open Questions

- Should `hmac_hash` support a optional `prefix` for downstream namespace
  tagging? — defer unless a customer requests it in beta.
