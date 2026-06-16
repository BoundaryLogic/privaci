"""Deterministic salt-hashed fake value generation.

Public surface for the faker engine, provider registry, and extension API.
See ``deterministic-faker/spec.md`` and ``docs/configuration.md#actions``.
"""

from __future__ import annotations

from privaci.mask.faker.base import FakeProvider
from privaci.mask.faker.context import FakeRequest
from privaci.mask.faker.engine import generate_fake
from privaci.mask.faker.hash import compute_seed, normalize_input, seed_to_index
from privaci.mask.faker.registry import (
    get_provider,
    known_providers,
    register_provider,
    validate_fake_providers,
)

__all__ = [
    "FakeProvider",
    "FakeRequest",
    "compute_seed",
    "generate_fake",
    "get_provider",
    "known_providers",
    "normalize_input",
    "register_provider",
    "seed_to_index",
    "validate_fake_providers",
]
