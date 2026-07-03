## Why

`validate_keyed_actions` currently gates keyed masking actions (`hmac_hash`, `pseudonym`) by
matching `LicenseStatus.tier` against a hard-coded set of license-tier name strings baked into
the public engine. This is wrong on two counts:

- **`is_valid` cannot be the gate.** The community fallback returns
  `LicenseStatus(tier="community", is_valid=True)` — "the OSS engine may run" — so `is_valid`
  alone cannot distinguish an unentitled community install from an entitled plugin. Overloading
  it would hand keyed actions to the pure ELv2 engine for free.
- **Tier-name strings do not belong in the public engine.** The current allow-set only "works"
  by accident (community happens to be absent from it) and couples the public engine to a
  plugin's private naming. It is a blocklist (every future value must be remembered) where an
  allowlist is correct.

The fix is additive and capability-oriented: give `LicenseStatus` a `capabilities:
frozenset[str]` field of opaque capability tokens, and gate keyed actions on **membership**
(`"keyed_actions" in status.capabilities`). The public contract knows only capability tokens;
the installed `LicenseValidator` is the sole thing that populates them; the community fallback
leaves the set empty. One field, one gate, no plugin tier names in the public repo.

## What Changes

- **`LicenseStatus`** gains `capabilities: frozenset[str] = frozenset()` (additive, backward
  compatible — a default-valued field, no contract major bump).
- **`CommunityLicenseValidator`** returns an empty `capabilities` set (explicit).
- **`validate_keyed_actions`** checks `"keyed_actions" in status.capabilities` instead of
  matching `tier` against hard-coded tier-name strings. The `_normalize_license_tier` helper
  and the tier-name allow-set are removed.
- **Docs**: `docs/extending-privaci.md` documents the `capabilities` field and the
  `keyed_actions` token for plugin authors; `docs/configuration.md` keyed-action remediation
  updated to reference capability entitlement. CHANGELOG entry.
- **ADR tombstones**: mark the `docs/adr/0003` tombstone superseded and add a forward tombstone
  pointer for `docs/adr/0012` (business detail stays private).

## Capabilities

### Modified

- `commercial-tier-contract`: `LicenseStatus` carries capability tokens; keyed-action gating is
  by capability membership, not tier-name matching; community capabilities are empty.

## Impact

- **Additive contract field** — older plugin builds that construct `LicenseStatus` without
  `capabilities` still work (default empty). A plugin that wants keyed actions must populate
  `capabilities` with `keyed_actions`.
- **Downstream plugin** consumes this field to gate keyed and other license-gated features by
  capability token (tracked in the plugin repo). Sequence this change first (or same release).
- **Security**: fail-closed unchanged — no capability token ⇒ keyed actions rejected with exit
  5. No new network calls; the public engine still never phones home.

## Non-goals

- Enumerating every capability token here — only `keyed_actions` is consumed by the public
  engine today; other tokens are defined and enforced by the installed plugin.
- Any pricing, tier, or entitlement-transport decisions (private to the plugin repo).
