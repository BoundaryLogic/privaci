"""Salted hash primitives for deterministic fake generation.

Implements the seed formula from ``deterministic-faker/spec.md``:

    seed  = sha256(salt || column_path || normalized_input).digest()[:16]
    index = int.from_bytes(seed, 'big') % len(fake_library)
"""

from __future__ import annotations

import hashlib
import unicodedata

_SEED_BYTE_LENGTH = 16


def normalize_input(value: str) -> str:
    """Return unicode-normalized (NFC), case-preserved input for hashing."""
    return unicodedata.normalize("NFC", value)


def _encode_segment(value: str) -> bytes:
    """Length-prefix a UTF-8 segment so concatenation cannot shift boundaries."""
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, byteorder="big") + encoded


def compute_seed(salt: str, column_path: str, normalized_input: str) -> bytes:
    """Derive the 16-byte seed for one (salt, column, value) triple."""
    digest = hashlib.sha256()
    digest.update(_encode_segment(salt))
    digest.update(_encode_segment(column_path))
    digest.update(_encode_segment(normalized_input))
    return digest.digest()[:_SEED_BYTE_LENGTH]


def seed_to_index(seed: bytes, library_size: int) -> int:
    """Map a seed to a library index in ``[0, library_size)``."""
    if library_size < 1:
        msg = "library_size must be >= 1"
        raise ValueError(msg)
    return int.from_bytes(seed, byteorder="big") % library_size


def seed_to_int(seed: bytes) -> int:
    """Return the seed as a big-endian integer (used by numeric providers)."""
    return int.from_bytes(seed, byteorder="big")
