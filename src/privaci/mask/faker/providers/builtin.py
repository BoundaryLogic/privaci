"""Built-in deterministic fake providers."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from privaci.mask.faker.base import FakeProvider
from privaci.mask.faker.hash import seed_to_index, seed_to_int
from privaci.mask.faker.libraries import (
    CITIES,
    COMPANIES,
    COUNTRIES,
    CREDIT_CARD_BINS,
    DEFAULT_EMAIL_DOMAINS,
    EMAIL_LOCALS,
    FIRST_NAMES,
    JOB_TITLES,
    LAST_NAMES,
    POSTCODES,
    STREETS,
    USERNAMES,
)

_TEST_PASSWORD = "privaci-test-" + "pw"  # documented fixed placeholder, not a secret


def _luhn_check_digit(partial: str) -> int:
    """Compute the Luhn check digit for all digits except the last."""
    total = 0
    for index, ch in enumerate(reversed(partial)):
        digit = int(ch)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - (total % 10)) % 10


def passes_luhn(number: str) -> bool:
    """Return whether ``number`` satisfies the Luhn checksum."""
    if not number.isdigit() or len(number) < 2:
        return False
    expected = int(number[-1])
    return _luhn_check_digit(number[:-1]) == expected


_PHONE_RE = re.compile(r"^\+?(\d{1,3})?")
_DOB_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class LibraryProvider(FakeProvider):
    """Pick a value from a static library using ``seed_to_index``."""

    def __init__(self, name: str, library: tuple[str, ...]) -> None:
        self.name = name
        self._library = library

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        return self._library[seed_to_index(seed, len(self._library))]


class FullNameProvider(FakeProvider):
    """Combine independent first/last picks into a full name."""

    name = "full_name"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        first = FIRST_NAMES[seed_to_index(seed, len(FIRST_NAMES))]
        last_seed = seed[::-1]
        last = LAST_NAMES[seed_to_index(last_seed, len(LAST_NAMES))]
        return f"{first} {last}"


class EmailProvider(FakeProvider):
    """Build ``local@domain`` from static libraries."""

    name = "email"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        local = EMAIL_LOCALS[seed_to_index(seed, len(EMAIL_LOCALS))]
        domain = self._resolve_domain(seed, params)
        return f"{local}@{domain}"

    def _resolve_domain(self, seed: bytes, params: dict[str, str]) -> str:
        if "domain" in params:
            return params["domain"]
        domains = DEFAULT_EMAIL_DOMAINS
        return domains[seed_to_index(seed[4:], len(domains))]


class AddressProvider(FakeProvider):
    """Single-line street + city + postcode + country."""

    name = "address"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        street = STREETS[seed_to_index(seed, len(STREETS))]
        city = CITIES[seed_to_index(seed[1:], len(CITIES))]
        postcode = POSTCODES[seed_to_index(seed[2:], len(POSTCODES))]
        country = COUNTRIES[seed_to_index(seed[3:], len(COUNTRIES))]
        return f"{street}, {city} {postcode}, {country}"


class PhoneProvider(FakeProvider):
    """E.164-style test number; preserves leading country code when present."""

    name = "phone"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        country = self._detect_country_code(value)
        digits = f"{seed_to_int(seed) % 10_000_000_000:010d}"
        if country:
            return f"+{country}{digits[-10:]}"
        return f"+1{digits[-10:]}"

    def _detect_country_code(self, value: str) -> str | None:
        match = _PHONE_RE.match(value.strip())
        if not match or not match.group(1):
            return None
        return match.group(1)


class DobProvider(FakeProvider):
    """ISO-8601 date within ±5 years of the input age bracket."""

    name = "dob"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        anchor = self._parse_input_date(value) or date(1985, 6, 15)
        today = date.today()
        age = (today - anchor).days // 365
        offset_years = (seed_to_int(seed) % 11) - 5
        fake_age = max(0, age + offset_years)
        fake_dob = today - timedelta(days=fake_age * 365 + (seed[0] % 365))
        return fake_dob.isoformat()

    def _parse_input_date(self, value: str) -> date | None:
        match = _DOB_RE.match(value.strip())
        if not match:
            return None
        return date(int(match[1]), int(match[2]), int(match[3]))


class IpAddressProvider(FakeProvider):
    """RFC 5737 TEST-NET addresses."""

    name = "ip_address"

    _BLOCKS: tuple[str, ...] = ("192.0.2", "198.51.100", "203.0.113")

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        block = self._BLOCKS[seed_to_index(seed, len(self._BLOCKS))]
        host = seed[0] % 254 + 1
        return f"{block}.{host}"


class SsnProvider(FakeProvider):
    """SSA-advertising test range ``000-99-XXXX`` (area 000–099)."""

    name = "ssn"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        area = seed_to_int(seed) % 100
        group = seed[4] % 100
        serial = seed_to_int(seed[8:]) % 10_000
        return f"{area:03d}-{group:02d}-{serial:04d}"


def is_fake_ssn(value: str) -> bool:
    """Return whether ``value`` is in the SSA advertising test structure."""
    match = re.match(r"^(\d{3})-(\d{2})-(\d{4})$", value)
    if not match:
        return False
    area = int(match[1])
    return area <= 99


class CreditCardProvider(FakeProvider):
    """Luhn-valid card from documented test BINs."""

    name = "credit_card"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        bin_code = CREDIT_CARD_BINS[seed_to_index(seed, len(CREDIT_CARD_BINS))]
        total_len = 15 if bin_code.startswith("37") else 16
        body_len = total_len - len(bin_code) - 1
        suffix = seed_to_int(seed[2:]) % (10**body_len)
        partial = f"{bin_code}{suffix:0{body_len}d}"
        check = _luhn_check_digit(partial)
        return partial + str(check)


class UuidProvider(FakeProvider):
    """Deterministic UUIDv4 layout from the seed bytes."""

    name = "uuid"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        padded = (seed * 2)[:16]
        raw = bytearray(padded)
        raw[6] = (raw[6] & 0x0F) | 0x40
        raw[8] = (raw[8] & 0x3F) | 0x80
        return str(uuid.UUID(bytes=bytes(raw)))


class PasswordProvider(FakeProvider):
    """Always emit the fixed test placeholder — never a real-looking hash."""

    name = "password"

    def generate(self, seed: bytes, value: str, *, params: dict[str, str]) -> str:
        return _TEST_PASSWORD


def builtin_providers() -> tuple[FakeProvider, ...]:
    """Return every built-in provider instance for registry bootstrap."""
    return (
        LibraryProvider("first_name", FIRST_NAMES),
        LibraryProvider("last_name", LAST_NAMES),
        FullNameProvider(),
        EmailProvider(),
        LibraryProvider("street", STREETS),
        AddressProvider(),
        LibraryProvider("city", CITIES),
        LibraryProvider("postcode", POSTCODES),
        LibraryProvider("country", COUNTRIES),
        PhoneProvider(),
        DobProvider(),
        IpAddressProvider(),
        SsnProvider(),
        CreditCardProvider(),
        UuidProvider(),
        LibraryProvider("company", COMPANIES),
        LibraryProvider("job_title", JOB_TITLES),
        LibraryProvider("username", USERNAMES),
        PasswordProvider(),
    )
