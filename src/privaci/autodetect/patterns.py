"""Built-in PII column-name pattern library."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PatternKind = Literal[
    "substring",
    "bounded_substring",
    "suffix",
    "prefix",
    "regex",
    "wildcard_prefix",
]


@dataclass(frozen=True, slots=True)
class PatternRule:
    """One auto-detect pattern entry."""

    rule_id: str
    kind: PatternKind
    pattern: str
    provider: str | None
    action: Literal["fake", "hash", "static", "ner_mask"]
    static_value: str | None = None


_STATIC_PASSWORD = (
    "privaci-test-pw"  # noqa: S105 — documented test placeholder, not a secret
)

# SECURITY: fixed test placeholder for password columns — never a real hash.
BUILTIN_PATTERNS: tuple[PatternRule, ...] = (
    PatternRule("email_suffix", "suffix", "_email", "email", "fake"),
    PatternRule("email_prefix", "prefix", "email_", "email", "fake"),
    PatternRule("email", "substring", "email", "email", "fake"),
    PatternRule("e_mail", "substring", "e_mail", "email", "fake"),
    PatternRule("phone", "substring", "phone", "phone", "fake"),
    PatternRule("mobile", "substring", "mobile", "phone", "fake"),
    PatternRule("tel", "bounded_substring", "tel", "phone", "fake"),
    PatternRule("cell", "bounded_substring", "cell", "phone", "fake"),
    PatternRule("phone_suffix", "suffix", "_phone", "phone", "fake"),
    PatternRule("ssn", "substring", "ssn", "ssn", "fake"),
    PatternRule("social_security", "substring", "social_security", "ssn", "fake"),
    PatternRule("tax_id", "substring", "tax_id", "ssn", "fake"),
    PatternRule("national_id", "substring", "national_id", "ssn", "fake"),
    PatternRule("first_name", "substring", "first_name", "first_name", "fake"),
    PatternRule("fname", "substring", "fname", "first_name", "fake"),
    PatternRule("given_name", "substring", "given_name", "first_name", "fake"),
    PatternRule("last_name", "substring", "last_name", "last_name", "fake"),
    PatternRule("lname", "substring", "lname", "last_name", "fake"),
    PatternRule("surname", "substring", "surname", "last_name", "fake"),
    PatternRule("family_name", "substring", "family_name", "last_name", "fake"),
    PatternRule("full_name", "substring", "full_name", "full_name", "fake"),
    PatternRule("display_name", "substring", "display_name", "full_name", "fake"),
    PatternRule("name_exact", "regex", r"^name$", "full_name", "fake"),
    # IP rules precede the generic `address` substring so `ip_address` is not
    # mis-matched as a street address. `ip` is word-anchored to avoid matching
    # substrings like `descr(ip)tion` or `sh(ip)ping`.
    PatternRule("ip_address", "substring", "ip_address", "ip_address", "fake"),
    PatternRule("ip_suffix", "suffix", "_ip", "ip_address", "fake"),
    PatternRule("ip_prefix", "prefix", "ip_", "ip_address", "fake"),
    PatternRule("ip_exact", "regex", r"^ip$", "ip_address", "fake"),
    PatternRule("address", "substring", "address", "address", "fake"),
    PatternRule("street", "substring", "street", "street", "fake"),
    PatternRule("city", "substring", "city", "city", "fake"),
    PatternRule("postcode", "substring", "postcode", "postcode", "fake"),
    PatternRule("zip", "substring", "zip", "postcode", "fake"),
    PatternRule("country", "substring", "country", "country", "fake"),
    PatternRule("dob", "substring", "dob", "dob", "fake"),
    PatternRule("date_of_birth", "substring", "date_of_birth", "dob", "fake"),
    PatternRule("birth_date", "substring", "birth_date", "dob", "fake"),
    PatternRule("birthday", "substring", "birthday", "dob", "fake"),
    PatternRule("credit_card", "substring", "credit_card", "credit_card", "fake"),
    PatternRule("card_number", "substring", "card_number", "credit_card", "fake"),
    PatternRule("cc_number", "substring", "cc_number", "credit_card", "fake"),
    PatternRule("pan", "bounded_substring", "pan", "credit_card", "fake"),
    PatternRule(
        "password_hash",
        "substring",
        "password_hash",
        "password",
        "static",
        _STATIC_PASSWORD,
    ),
    PatternRule(
        "password", "substring", "password", "password", "static", _STATIC_PASSWORD
    ),
    PatternRule(
        "passwd", "substring", "passwd", "password", "static", _STATIC_PASSWORD
    ),
    PatternRule("pwd", "substring", "pwd", "password", "static", _STATIC_PASSWORD),
    PatternRule("token", "substring", "token", None, "hash"),
    PatternRule("api_key", "substring", "api_key", None, "hash"),
    PatternRule("secret", "substring", "secret", None, "hash"),
    PatternRule("token_suffix", "suffix", "_token", None, "hash"),
    PatternRule("auth_prefix", "prefix", "auth_", None, "hash"),
    PatternRule("notes_suffix", "suffix", "_notes", None, "ner_mask"),
    PatternRule("notes_substring", "substring", "notes", None, "ner_mask"),
    PatternRule("notes", "wildcard_prefix", "note", None, "ner_mask"),
    PatternRule("comments", "wildcard_prefix", "comment", None, "ner_mask"),
    PatternRule("description", "substring", "description", None, "ner_mask"),
    PatternRule("bio", "substring", "bio", None, "ner_mask"),
    PatternRule("about", "substring", "about", None, "ner_mask"),
)

_COMPILED_REGEX: dict[str, re.Pattern[str]] = {}


def compile_patterns() -> dict[str, re.Pattern[str]]:
    """Return cached compiled regex rules keyed by rule id."""
    if not _COMPILED_REGEX:
        for rule in BUILTIN_PATTERNS:
            if rule.kind == "regex":
                _COMPILED_REGEX[rule.rule_id] = re.compile(rule.pattern, re.IGNORECASE)
    return _COMPILED_REGEX
