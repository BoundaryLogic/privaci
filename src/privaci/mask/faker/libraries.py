"""Static fake-value libraries for built-in providers.

Every entry is synthetic and obviously non-production. Libraries are tuples so
they are immutable and hashable at import time.
"""

from __future__ import annotations

DEFAULT_EMAIL_DOMAINS: tuple[str, ...] = (
    "fakedom.net",
    "example.test",
    "tryvault.dev",
)

FIRST_NAMES: tuple[str, ...] = (
    "Alex",
    "Blake",
    "Casey",
    "Drew",
    "Ellis",
    "Finley",
    "Gray",
    "Harper",
    "Indigo",
    "Jordan",
    "Kai",
    "Logan",
    "Morgan",
    "Noel",
    "Parker",
    "Quinn",
    "Riley",
    "Sage",
    "Taylor",
    "Uma",
    "Vale",
    "Winter",
    "Xen",
    "Yael",
    "Zion",
)

LAST_NAMES: tuple[str, ...] = (
    "Abbott",
    "Bennett",
    "Carter",
    "Delaney",
    "Ellison",
    "Foster",
    "Garcia",
    "Hayes",
    "Ingram",
    "Jensen",
    "Keller",
    "Lopez",
    "Monroe",
    "Nash",
    "Owens",
    "Perez",
    "Quincy",
    "Rivera",
    "Sutton",
    "Turner",
    "Underwood",
    "Vargas",
    "Walsh",
    "Xu",
    "Young",
)

EMAIL_LOCALS: tuple[str, ...] = (
    "alex.rivera",
    "blake.chen",
    "casey.morgan",
    "drew.patel",
    "ellis.kim",
    "finley.ross",
    "gray.singh",
    "harper.lee",
    "jordan.walsh",
    "kai.nguyen",
    "logan.brooks",
    "morgan.diaz",
    "noel.fischer",
    "parker.hughes",
    "quinn.baker",
    "riley.cooper",
    "sage.murphy",
    "taylor.price",
    "uma.reed",
    "vale.stone",
)

STREETS: tuple[str, ...] = (
    "100 Maple Lane",
    "200 Oak Street",
    "300 Cedar Avenue",
    "400 Birch Road",
    "500 Pine Court",
    "600 Elm Drive",
    "700 Willow Way",
    "800 Aspen Place",
    "900 Spruce Terrace",
    "1010 Redwood Blvd",
)

CITIES: tuple[str, ...] = (
    "Northgate",
    "Southfield",
    "Eastbrook",
    "Westhaven",
    "Lakeside",
    "Riverton",
    "Hillcrest",
    "Fairview",
    "Brookdale",
    "Greenport",
)

POSTCODES: tuple[str, ...] = (
    "10001",
    "20002",
    "30303",
    "44104",
    "60605",
    "77006",
    "85007",
    "98108",
    "02109",
    "19110",
)

COUNTRIES: tuple[str, ...] = (
    "US",
    "CA",
    "GB",
    "DE",
    "FR",
    "AU",
    "NZ",
    "IE",
    "NL",
    "SE",
)

COMPANIES: tuple[str, ...] = (
    "Acme Health Systems",
    "Blue Ridge Analytics",
    "Cedar Point Software",
    "Delta Care Partners",
    "Evergreen Data Co",
    "Frontier Logic LLC",
    "Granite Bridge Inc",
    "Harbor View Labs",
    "Ironwood Services",
    "Juniper Networks Test",
)

JOB_TITLES: tuple[str, ...] = (
    "Software Engineer",
    "Data Analyst",
    "Product Manager",
    "Support Specialist",
    "Clinical Coordinator",
    "Operations Lead",
    "Security Analyst",
    "DevOps Engineer",
    "QA Tester",
    "Account Manager",
)

USERNAMES: tuple[str, ...] = (
    "alexr42",
    "blake_c",
    "casey.dev",
    "drew99",
    "ellis_k",
    "finley.m",
    "gray_ops",
    "harper_q",
    "jordanx",
    "kai_labs",
)

# Documented test BINs — never real issuer ranges.
CREDIT_CARD_BINS: tuple[str, ...] = (
    "411111",
    "424242",
    "555555",
    "378282",
    "601111",
)
