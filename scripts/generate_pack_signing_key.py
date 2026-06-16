#!/usr/bin/env python3
"""Generate an Ed25519 keypair for config-pack signing.

Prints the private and public keys as hex. Store the private key in the release
secret store only (e.g. GitHub Actions ``PACK_SIGNING_PRIVATE_KEY``). Publish
the public key in release notes and configure runtimes with
``PRIVACI_PACK_PUBLIC_KEY``.

Run: ``python scripts/generate_pack_signing_key.py``

See: ``docs/runbooks/pack-signing.md``
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    """Generate and print a fresh Ed25519 keypair."""
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
    print("PRIVATE_KEY_HEX:", priv_bytes.hex())
    print("PUBLIC_KEY_HEX :", pub_bytes.hex())
    print()
    print("Store PRIVATE_KEY_HEX in release secrets only — never commit it.")
    print("Set PUBLIC_KEY_HEX as PRIVACI_PACK_PUBLIC_KEY on runtimes.")


if __name__ == "__main__":
    main()
