## 1. Config & validation

- [ ] 1.1 Add `PseudonymKeyAction` params and top-level `pseudonym_key` field (secret URI)
- [ ] 1.2 Extend action discriminated union with `hmac_hash` and `pseudonym`
- [ ] 1.3 Require `pseudonym_key` when any column uses keyed actions; min 32 bytes post-resolution
- [ ] 1.4 Wire Growth+ tier gate at `validate` (exit `5` for starter/community)
- [ ] 1.5 Export JSON Schema; update `privaci migrate-config` scaffold if config version bumps

## 2. Masking implementation

- [ ] 2.1 Implement `normalize_for_hmac(value) -> bytes` shared helper
- [ ] 2.2 Implement `hmac_hash` handler with hex/base64url encoding option
- [ ] 2.3 Implement `pseudonym` handler using HMAC seed + existing `FakeProvider` registry
- [ ] 2.4 Wire UNIQUE-aware suffix path for keyed pseudonym (reuse faker collision logic)
- [ ] 2.5 Audit-log entries for keyed actions (action type only — never key or raw value)

## 3. Secrets & boot

- [ ] 3.1 Resolve `pseudonym_key` via secrets resolver; wrap in `SecretStr`
- [ ] 3.2 Add `PSEUDONYM_KEY` to `.env.example` and docs

## 4. Tests & docs

- [ ] 4.1 Unit tests: determinism, key rotation changes output, column-path isolation
- [ ] 4.2 Negative tests: missing key, short key, starter tier rejection
- [ ] 4.3 Property tests (`hypothesis`) for cross-row FK consistency with `seed_alias`
- [ ] 4.4 Update `docs/configuration.md`, `CHANGELOG.md`
