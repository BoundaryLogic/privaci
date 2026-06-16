"""Ed25519 manifest signature verification for config packs."""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from privaci.errors import ConfigError
from privaci.packs.keys import PACK_PUBLIC_KEY_ENV, load_trusted_pack_public_key

SIGNATURE_FIELD = "signature"


def canonical_payload(manifest: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 bytes for signing or verification."""
    unsigned = {key: value for key, value in manifest.items() if key != SIGNATURE_FIELD}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()


def verify_manifest_signature(
    manifest: dict[str, Any],
    *,
    public_key: Ed25519PublicKey | None = None,
) -> None:
    """Verify the detached Ed25519 signature on ``manifest``.

    Raises:
        ConfigError: When the signature field is missing or invalid.
    """
    signature_b64 = manifest.get(SIGNATURE_FIELD)
    if not isinstance(signature_b64, str) or not signature_b64:
        raise ConfigError(
            "Verifying config pack manifest",
            cause="Manifest is missing a base64 Ed25519 signature.",
            remediation="Fetch the pack from the official registry only.",
        )
    key = public_key or _resolve_trusted_key()
    try:
        key.verify(base64.b64decode(signature_b64), canonical_payload(manifest))
    except (InvalidSignature, ValueError) as exc:
        raise ConfigError(
            "Verifying config pack manifest",
            cause="Manifest signature does not verify against the trusted public key.",
            remediation="Do not install unsigned or tampered packs.",
        ) from exc


def _resolve_trusted_key() -> Ed25519PublicKey:
    """Return the injected trust anchor, or fail closed when none is configured."""
    trusted = load_trusted_pack_public_key()
    if trusted is None:
        raise ConfigError(
            "Verifying config pack manifest",
            cause="No trusted config-pack public key is configured.",
            remediation=(
                f"Set {PACK_PUBLIC_KEY_ENV} to the official release key before "
                "installing packs; see docs/configuration.md#installing-a-config-pack."
            ),
        )
    return Ed25519PublicKey.from_public_bytes(trusted)
