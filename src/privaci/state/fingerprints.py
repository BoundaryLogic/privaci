"""Deterministic identity helpers for run state.

Computes the non-reversible fingerprints stored in ``_privaci.runs`` and a
time-ordered UUIDv7 for run/audit identifiers. None of these helpers accept or
emit raw secrets: the salt is reduced to a 16-char fingerprint, and the source
URL is reduced to ``<host>:<port>/<dbname>`` before hashing.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from urllib.parse import unquote, urlsplit

from privaci.config import Config

_SALT_FINGERPRINT_LENGTH = 16
_DEFAULT_PG_PORT = 5432


def salt_fingerprint(salt: str) -> str:
    """Return ``sha256(salt)[:16]`` — a non-reversible salt identifier.

    Args:
        salt: The anonymization salt. Never logged or stored verbatim.

    Returns:
        The first 16 hex characters of the salt's SHA-256 digest.
    """
    digest = hashlib.sha256(salt.encode("utf-8")).hexdigest()
    return digest[:_SALT_FINGERPRINT_LENGTH]


def source_db_hash(source_url: str) -> str:
    """Return ``sha256("<host>:<port>/<dbname>")`` for billing/resume identity.

    The same host+port+database always yields the same hash; a different
    database name on the same host yields a different hash. Credentials and
    query parameters are excluded.

    Args:
        source_url: A ``postgres://`` connection URL.

    Returns:
        The hex SHA-256 digest of the canonical ``host:port/dbname`` string.
    """
    parts = urlsplit(source_url)
    host = (parts.hostname or "").lower()
    port = parts.port or _DEFAULT_PG_PORT
    dbname = unquote(parts.path.lstrip("/"))
    canonical = f"{host}:{port}/{dbname}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def config_hash(config: Config) -> str:
    """Return the SHA-256 of the canonicalized config JSON.

    Two semantically identical configs produce the same hash regardless of key
    ordering in the source YAML.

    Args:
        config: The validated configuration document.

    Returns:
        The hex SHA-256 digest of the canonical config JSON.
    """
    payload = config.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_uuid7() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 per RFC 9562.

    The leading 48 bits encode Unix time in milliseconds, making identifiers
    sortable by creation time, which keeps ``runs`` and ``audit_log`` primary
    keys index-friendly.

    Returns:
        A version-7 :class:`uuid.UUID`.
    """
    unix_ms = int(time.time() * 1000)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (unix_ms & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0x2 << 62  # RFC 9562 variant bits (10xx).
    value |= rand_b
    return uuid.UUID(int=value)
