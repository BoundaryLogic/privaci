"""UNIQUE-constraint-aware suffix strategies.

When a column participates in a UNIQUE constraint the base library pick may
collide across many distinct inputs. A stable hex suffix derived from the seed
makes outputs collision-resistant while preserving determinism.

The suffix is 16 hex characters (64 bits) so that birthday collisions stay
negligible across realistic table sizes: at 1M distinct inputs the collision
probability is ~3e-8, satisfying the deterministic-faker spec's "1M distinct
masked emails, no collisions" scenario. A shorter token (e.g. 24 bits) would
birthday-collide at only a few thousand rows.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

# 16 hex chars == 64 bits. See module docstring for the collision analysis.
_SUFFIX_LENGTH = 16
_NUMERIC_RE = re.compile(r"^-?\d+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def uniqueness_suffix(seed: bytes) -> str:
    """Return a stable 16-character hex token (64 bits) from the seed."""
    return seed.hex()[:_SUFFIX_LENGTH]


def apply_uniqueness(
    base: str,
    seed: bytes,
    *,
    provider: str,
) -> str:
    """Append a collision-resistant suffix appropriate to the provider type."""
    suffix = uniqueness_suffix(seed)
    if provider == "email":
        return _unique_email(base, suffix)
    if provider in {"uuid", "password"}:
        return base
    if provider == "dob" or _ISO_DATE_RE.match(base):
        return _unique_date(base, seed)
    if _NUMERIC_RE.match(base):
        return _unique_numeric(base, seed)
    return f"{base}__{suffix}"


def _unique_email(base: str, suffix: str) -> str:
    """Insert ``+suffix`` into the local part: ``user+abcd12@domain``."""
    if "@" not in base:
        return f"{base}+{suffix}"
    local, domain = base.rsplit("@", maxsplit=1)
    return f"{local}+{suffix}@{domain}"


def _unique_date(base: str, seed: bytes) -> str:
    """Shift an ISO date deterministically to satisfy UNIQUE without breaking type."""
    anchor = date.fromisoformat(base)
    offset_days = int.from_bytes(seed, byteorder="big") % 3650
    return (anchor + timedelta(days=offset_days + 1)).isoformat()


def _unique_numeric(base: str, seed: bytes) -> str:
    """Remap to a distinct integer while preserving digit width and sign."""
    negative = base.startswith("-")
    digits = base.lstrip("-")
    width = len(digits)
    if width == 0:
        return base
    space = 10**width
    offset = int.from_bytes(seed, byteorder="big") % space
    remapped = f"{offset:0{width}d}"[-width:]
    return f"-{remapped}" if negative else remapped
