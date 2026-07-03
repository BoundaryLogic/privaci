# Tasks: add-license-capabilities

## 1. Contract field

- [ ] 1.1 Add `capabilities: frozenset[str] = frozenset()` to `LicenseStatus`
      (`privaci/contracts/base.py`) with a docstring; keep `CONTRACT_VERSION` unchanged
- [ ] 1.2 `CommunityLicenseValidator.validate()` returns explicit `capabilities=frozenset()`
- [ ] 1.3 Confirm `privaci.contracts` re-exports unchanged; no other fallback touched

## 2. Keyed-action gate

- [ ] 2.1 `validate_keyed_actions` gates on `"keyed_actions" in status.capabilities`
- [ ] 2.2 Remove `_KEYED_ACTION_LICENSES` and `_normalize_license_tier`
- [ ] 2.3 Preserve exit-5 `LicenseError` (Context/Cause/Remediation) and exit-4
      `pseudonym_key` check ordering

## 3. Tests

- [ ] 3.1 `LicenseStatus` default capabilities empty; frozen equality/hash hold
- [ ] 3.2 Keyed config + capability present (+ key) → passes
- [ ] 3.3 Keyed config + capability absent → exit 5 (incl. community mode)
- [ ] 3.4 No keyed config → no-op regardless of capabilities
- [ ] 3.5 Register new test files in `scripts/capability_test/registry.py`

## 4. Docs + ADR tombstones

- [ ] 4.1 `docs/extending-privaci.md`: document `capabilities` field + `keyed_actions` token
      for plugin authors
- [ ] 4.2 `docs/configuration.md`: keyed-action remediation references capability entitlement
      (no tier-name strings)
- [ ] 4.3 `docs/adr/0003-*` tombstone: mark superseded; add `docs/adr/0012-*` forward tombstone
      pointer (pointer only)
- [ ] 4.4 CHANGELOG `[Unreleased]` entry (Changed)

## 5. Gates

- [ ] 5.1 `./scripts/ci-local.sh` green (black, isort, ruff, mypy --strict, guards, pytest)
- [ ] 5.2 `python scripts/check_public_repo_language.py --staged` clean (no tier names leaked)
