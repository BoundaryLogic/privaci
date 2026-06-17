"""Shared test constants — no magic strings in test bodies."""

from __future__ import annotations

import re

TEST_SALT = "a" * 64
MIN_SALT_LENGTH = 32
FAKE_EMAIL_DOMAIN = "fakedom.net"

SUPPORTED_CONFIG_VERSION = "1.0"
UNSUPPORTED_CONFIG_VERSION = "2.0"

# Ed25519 public key (hex) that verifies the fixture-signed packs under
# tests/fixtures/packs. This is a PUBLIC key — safe to commit; the matching
# private key is never stored in the repo. Tests inject it via
# PRIVACI_PACK_PUBLIC_KEY so production ships no embedded trust anchor.
FIXTURE_PACK_PUBLIC_KEY_HEX = (
    "60ec87519ccc63da75b3473670b44e83b6a8c559ac17667a9e9449afbd334b1d"
)

SSN_PATTERN = r"^\d{3}-\d{2}-\d{4}$"
SSN_REPLACEMENT = "000-00-0000"

# Deterministic Demo Corp mini-tier seed values (see 09_seed_data.sql).
DEMO_CORP_FORBIDDEN_EMAILS: tuple[str, ...] = (
    "user1@example.test",
    "user2@example.test",
    "billing1@example.test",
    "patient1@example.test",
)
DEMO_CORP_FORBIDDEN_SSNS: tuple[str, ...] = (
    "900-01-0001",
    "900-02-0002",
    "900-01-1001",
)
DEMO_CORP_FORBIDDEN_PHONES: tuple[str, ...] = ("555-0001", "555-0002")
DEMO_CORP_FORBIDDEN_FIRST_NAMES: tuple[str, ...] = ("First1", "First2", "Pat1")
DEMO_CORP_FORBIDDEN_ORG_NAMES: tuple[str, ...] = ("Org 1", "Org 2")
DEMO_CORP_FORBIDDEN_EINS: tuple[str, ...] = ("01-0000001", "02-0000002")
DEMO_CORP_FORBIDDEN_MRNS: tuple[str, ...] = ("MRN00000001", "MRN00000002")
DEMO_CORP_FORBIDDEN_INSURANCE_IDS: tuple[str, ...] = (
    "INS000000001",
    "INS000000002",
)
DEMO_CORP_FORBIDDEN_CARD_NUMBERS: tuple[str, ...] = (
    "4111-1111-1111-0001",
    "4111-1111-1111-0002",
)
DEMO_CORP_FORBIDDEN_PASSWORD_HASHES: tuple[str, ...] = (
    "hash-00000001",
    "hash-00000002",
)
DEMO_CORP_FORBIDDEN_NER_PHRASES: tuple[str, ...] = (
    "Pat1 Patient1",
    "MRN00000001",
    "First1 Last1",
    "Dr1 Provider1",
)
DEMO_CORP_STATIC_PASSWORD = "privaci-test-pw"
DEMO_CORP_HASH_HEX = re.compile(r"^[0-9a-f]{64}$")
DEMO_CORP_MASKED_EIN_PATTERN = re.compile(r"^00-000000\d$")
