"""Trusted Ed25519 public key for config-pack manifests.

The production trust anchor is provisioned at release time and injected through
the ``PRIVACI_PACK_PUBLIC_KEY`` environment variable (a hex-encoded 32-byte
Ed25519 public key). The engine intentionally ships **no** built-in key: a pack
is only trustworthy when the release pipeline (or operator) supplies the official
key, so signature verification fails closed when it is absent rather than
trusting a key embedded in source. Tests supply a fixture public key through the
same variable (see ``tests/fixtures/packs``).

See ``docs/configuration.md#installing-a-config-pack`` and the release runbook
for how the key is provisioned.
"""

from __future__ import annotations

import os

PACK_PUBLIC_KEY_ENV = "PRIVACI_PACK_PUBLIC_KEY"

_ED25519_PUBLIC_KEY_BYTES = 32


def load_trusted_pack_public_key() -> bytes | None:
    """Return the configured Ed25519 public-key bytes, or ``None`` if unset.

    Reads ``PRIVACI_PACK_PUBLIC_KEY`` and decodes it as hex. Returns ``None``
    when the variable is unset, empty, not valid hex, or not exactly 32 bytes,
    so callers fail closed instead of trusting a malformed anchor.
    """
    raw = os.environ.get(PACK_PUBLIC_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        return None
    if len(key) != _ED25519_PUBLIC_KEY_BYTES:
        return None
    return key
