"""Masking pipeline (L1 regex, L2 NER, deterministic faker)."""

from __future__ import annotations

from privaci.mask.faker import (
    FakeProvider,
    FakeRequest,
    generate_fake,
    register_provider,
)

__all__ = [
    "FakeProvider",
    "FakeRequest",
    "generate_fake",
    "register_provider",
]
