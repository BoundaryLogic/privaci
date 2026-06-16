# Runbook: Config-pack signing key

Config packs are JSON manifests signed with an Ed25519 key. The engine verifies
the signature against a **trusted public key** before merging a pack into a
local `mask-rules.yaml`. The engine ships no embedded key — the trust anchor is
provisioned at release time and injected at runtime via the
`PRIVACI_PACK_PUBLIC_KEY` environment variable. This runbook covers generating,
shipping, and rotating that key.

## Why there is no built-in key

A public key hardcoded in the source would let anyone holding the matching
private key forge packs the engine trusts. Keeping the anchor out of source and
injecting it at runtime means a leaked release artifact cannot be used to sign
malicious packs, and the key can be rotated without a code change.
`scripts/check_pack_key.py` fails CI/release if any 32-byte key literal appears
in `src/privaci/packs/keys.py`.

## Generate the keypair

```bash
python - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

private = Ed25519PrivateKey.generate()
public = private.public_key()

priv_bytes = private.private_bytes(
    serialization.Encoding.Raw,
    serialization.PrivateFormat.Raw,
    serialization.NoEncryption(),
)
pub_bytes = public.public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw,
)
print("PRIVATE_KEY_HEX:", priv_bytes.hex())  # store in release secrets only
print("PUBLIC_KEY_HEX :", pub_bytes.hex())   # publish in release notes
PY
```

## Current published key

| Released | Public key (hex) |
| --- | --- |
| `v0.1.0-beta.1`+ | `cd965cb6dadcecefd508ae84a000684f431490c3d3ddae006ad5f89bf2c25978` |

Operators set this as `PRIVACI_PACK_PUBLIC_KEY`. Update this table on each
rotation (see [Rotate the key](#rotate-the-key)).

## Provision for a release

Generate a keypair with the helper script (or the inline snippet below):

```bash
python scripts/generate_pack_signing_key.py
```

1. Store `PRIVATE_KEY_HEX` in the release secret store (GitHub Actions secret
   `PACK_SIGNING_PRIVATE_KEY`). Never commit it.
2. Publish `PUBLIC_KEY_HEX` in the GitHub release notes and in operator docs.
3. Configure runtimes to export the public key:

   ```bash
   export PRIVACI_PACK_PUBLIC_KEY="<PUBLIC_KEY_HEX>"
   ```

   For containers, set it as an environment variable in the deployment (Helm
   `values.yaml`, ECS task definition, etc.). It is **not** a secret.

## Sign a pack manifest

The signing pipeline computes the signature over the canonical JSON (all fields
except `signature`, `sort_keys=True`, compact separators — see
`privaci.packs.verify.canonical_payload`) and base64-encodes it into the
`signature` field.

## Verify behavior

| Situation | Result |
| --- | --- |
| `PRIVACI_PACK_PUBLIC_KEY` unset or invalid | `install-pack` exits `3`, no files modified |
| Key set, signature invalid/tampered | Exits `3`, no files modified |
| Key set, signature valid | Merge proceeds after preview/confirmation |

## Rotate the key

1. Generate a new keypair (above).
2. Re-sign all current packs with the new private key.
3. Publish the new public key and update runtime `PRIVACI_PACK_PUBLIC_KEY`.
4. Retire the old private key from the secret store.

Because the anchor is injected, rotation needs no engine release.

## Related

- [Installing a config pack](../configuration.md#installing-a-config-pack)
- [Exit code 3](../error-codes.md#exit-code-3-config-validation-failure)
