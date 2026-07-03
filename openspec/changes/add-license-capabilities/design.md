# Design: capability tokens on `LicenseStatus`

## The three states problem

The engine must distinguish three states, which `is_valid` + `tier` alone conflate:

| State | `is_valid` | May run OSS engine | Has keyed actions |
| --- | --- | --- | --- |
| Community (no plugin) | `True` | yes | **no** |
| Plugin, entitled for keyed | `True` | yes | **yes** |
| Plugin, not entitled | `False` | no (exit 5) | no |

`is_valid=True` is the "OSS engine may run" gate. A separate, positive signal is needed for
"this install may use keyed actions". That signal is a **capability token**.

## Contract change (`privaci/contracts/base.py`)

```python
@dataclass(frozen=True, slots=True)
class LicenseStatus:
    """Result of a license validation check."""

    tier: str
    is_valid: bool
    source_db_limit: int | None = None
    message: str | None = None
    capabilities: frozenset[str] = frozenset()
    """Opaque capability tokens the installed LicenseValidator grants. The engine
    checks membership only; it never interprets tier names. Empty in community mode."""
```

Additive, default-valued field → no `CONTRACT_VERSION` major bump (matches the
"backwards-compatible contract evolution" requirement). `frozenset()` is a safe immutable
default on a frozen/slots dataclass.

### Tokens the public engine reads

| Token | Gate |
| --- | --- |
| `keyed_actions` | `hmac_hash`, `pseudonym` in `validate_keyed_actions` |

Other tokens may exist but are defined and enforced entirely by the installed plugin; the
engine neither enumerates nor validates them.

## Gate change (`privaci/config/keyed.py`)

Before:

```python
license_tier = _normalize_license_tier(load_plugins().license_validator.validate().tier)
if license_tier not in _KEYED_ACTION_LICENSES:   # hard-coded tier-name allow-set
    raise LicenseError(...)
```

After:

```python
status = load_plugins().license_validator.validate()
if "keyed_actions" not in status.capabilities:
    raise LicenseError(...)   # same Context/Cause/Remediation, exit 5
```

Remove `_KEYED_ACTION_LICENSES` and `_normalize_license_tier` (tier-name normalization moves
entirely behind the plugin boundary — the engine no longer knows tier names). The
`pseudonym_key` presence check (exit 4) is unchanged and still runs after the capability gate.

## Fallback (`privaci/contracts/fallbacks.py`)

`CommunityLicenseValidator.validate()` returns
`LicenseStatus(tier="community", is_valid=True, capabilities=frozenset())` — explicit empty set
documents that community grants no license-gated capabilities.

## Failure modes (unchanged UX)

- Config declares keyed action, no `keyed_actions` capability → `LicenseError` exit **5**,
  naming the offending columns; remediation points to installing an entitling plugin or
  removing the action.
- `keyed_actions` present but no `pseudonym_key` → `SecretResolutionError` exit **4**.

## Compatibility

- A plugin built against the old contract (no `capabilities` kwarg) constructs `LicenseStatus`
  with the default empty set → keyed actions are rejected until it is rebuilt to grant the
  token. This is the correct fail-closed default.
- No engine behavior changes for configs without keyed actions.

## Testing

- `LicenseStatus` default `capabilities` is empty; equality/hash still hold (frozen).
- `validate_keyed_actions`: keyed config + capability present → passes (given key); keyed config
  + capability absent → exit 5; no keyed config → no-op regardless of capabilities.
- Community mode: keyed config → exit 5 (empty capabilities).
- A stub validator granting `keyed_actions` + configured key → passes.
