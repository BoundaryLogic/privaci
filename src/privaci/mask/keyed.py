"""Keyed HMAC masking primitives and pseudonym generation."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from privaci.errors import MaskingError
from privaci.mask.faker.context import FakeRequest
from privaci.mask.faker.hash import normalize_input
from privaci.mask.faker.registry import get_provider
from privaci.mask.faker.uniqueness import apply_uniqueness

_SEED_BYTE_LENGTH = 16


def normalize_for_hmac(value: Any) -> str:
    """Normalize a cell value for keyed HMAC input."""
    return normalize_input(str(value))


def compute_keyed_digest(
    pseudonym_key: str,
    column_path: str,
    normalized_input: str,
) -> bytes:
    """Return HMAC-SHA256 over the column path and normalized value."""
    message = _encode_segment(column_path) + _encode_segment(normalized_input)
    return hmac.new(
        pseudonym_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()


def encode_keyed_digest(digest: bytes, *, encoding: str) -> str:
    """Encode a keyed digest as hex or base64url."""
    if encoding == "base64url":
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    if encoding == "hex":
        return digest.hex()
    msg = f"Unsupported hmac_hash encoding: {encoding!r}"
    raise MaskingError(msg)


def generate_keyed_pseudonym(request: FakeRequest, *, pseudonym_key: str) -> str:
    """Generate a deterministic keyed pseudonym using a fake provider."""
    normalized = normalize_input(request.value)
    if not normalized:
        return normalized

    seed = compute_keyed_digest(
        pseudonym_key,
        request.hash_path,
        normalized,
    )[:_SEED_BYTE_LENGTH]
    try:
        provider = get_provider(request.provider)
    except KeyError as exc:
        raise MaskingError(
            f"Generating pseudonym for {request.column_path}",
            cause=f"Unknown provider {request.provider!r}.",
            remediation="Register the provider or fix mask-rules.yaml.",
        ) from exc

    base = provider.generate(seed, normalized, params=request.params)
    if request.is_unique:
        return apply_uniqueness(base, seed, provider=request.provider)
    return base


def _encode_segment(value: str) -> bytes:
    """Length-prefix a UTF-8 segment so concatenation cannot shift boundaries."""
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, byteorder="big") + encoded
