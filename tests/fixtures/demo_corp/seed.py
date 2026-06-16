"""Deterministic seeding for fixture generation."""

from __future__ import annotations

import random
import re
from typing import Final

from tests.fixtures.demo_corp.tiers import FIXTURE_SEED

_FAKE_DOMAIN: Final[str] = "example.test"
_BANNED_EMAIL_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"@gmail\.com$", re.I),
    re.compile(r"@yahoo\.com$", re.I),
    re.compile(r"@acme\.", re.I),
)


def reset_seed() -> None:
    """Reset ``random`` to the fixture seed for deterministic generation."""
    random.seed(FIXTURE_SEED)


def fixture_email(prefix: str, index: int) -> str:
    """Build a deterministic, obviously synthetic email address."""
    email = f"{prefix}{index}@{_FAKE_DOMAIN}"
    _assert_not_real_pii(email)
    return email


def fixture_ssn(index: int) -> str:
    """Return an invalid SSA-range SSN (900-xx-xxxx) for synthetic data."""
    return f"900-{index % 100:02d}-{index % 10000:04d}"


def fixture_phone(index: int) -> str:
    """Return a deterministic fake phone number."""
    return f"555-{index % 10000:04d}"


def _assert_not_real_pii(value: str) -> None:
    """Reject values that look like real-world PII domains."""
    for pattern in _BANNED_EMAIL_PATTERNS:
        if pattern.search(value):
            msg = "Fixture generator produced a banned PII-like value"
            raise ValueError(msg)
