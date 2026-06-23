## 1. Config & validation

- [x] 1.1 Add `PseudonymKeyAction` params and top-level `pseudonym_key` field (secret URI)
- [x] 1.2 Extend action discriminated union with `hmac_hash` and `pseudonym`
- [x] 1.3 Require `pseudonym_key` when any column uses keyed actions; min 32 bytes post-resolution
- [x] 1.4 Wire Growth+ tier gate at `validate` (exit `5` for starter/community)
- [x] 1.5 Export JSON Schema; update `privaci migrate-config` scaffold if config version bumps

## 2. Masking implementation

- [x] 2.1 Implement `normalize_for_hmac(value) -> bytes` shared helper
- [x] 2.2 Implement `hmac_hash` handler with hex/base64url encoding option
- [x] 2.3 Implement `pseudonym` handler using HMAC seed + existing `FakeProvider` registry
- [x] 2.4 Wire UNIQUE-aware suffix path for keyed pseudonym (reuse faker collision logic)
- [x] 2.5 Audit-log entries for keyed actions (action type only — never key or raw value)

## 3. Secrets & boot

- [x] 3.1 Resolve `pseudonym_key` via secrets resolver; wrap in `SecretStr`
- [x] 3.2 Add `PSEUDONYM_KEY` to `.env.example` and docs

## 4. Tests & docs

- [x] 4.1 Unit tests: determinism, key rotation changes output, column-path isolation
- [x] 4.2 Negative tests: missing key, starter tier rejection
- [ ] 4.3 Property tests (`hypothesis`) for cross-row FK consistency with `seed_alias`
- [x] 4.4 Update `docs/configuration.md`, `CHANGELOG.md`
