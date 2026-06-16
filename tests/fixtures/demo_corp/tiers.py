"""Scale parameters per fixture tier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

FIXTURE_SEED: Final[int] = 42


class TierName(StrEnum):
    """Named fixture tiers from ``docs/test-fixtures.md``."""

    MINI = "mini"
    DEMO = "demo"
    STRESS = "stress"


@dataclass(frozen=True, slots=True)
class TierParams:
    """Row counts for each generated entity."""

    organizations: int
    users: int
    employees: int
    providers: int
    patients: int
    patient_visits: int
    prescriptions: int
    patient_documents: int
    tickets: int
    ticket_messages: int
    invoices: int
    invoice_line_items: int
    raw_events: int
    comments: int
    subscriptions: int
    user_addresses: int
    user_payment_methods: int
    api_keys: int
    sessions: int
    audit_events: int


_TIERS: dict[TierName, TierParams] = {
    TierName.MINI: TierParams(
        organizations=20,
        users=200,
        employees=50,
        providers=30,
        patients=300,
        patient_visits=500,
        prescriptions=200,
        patient_documents=50,
        tickets=100,
        ticket_messages=500,
        invoices=40,
        invoice_line_items=120,
        raw_events=2_000,
        comments=200,
        subscriptions=20,
        user_addresses=200,
        user_payment_methods=80,
        api_keys=100,
        sessions=300,
        audit_events=500,
    ),
    TierName.DEMO: TierParams(
        organizations=500,
        users=10_000,
        employees=5_000,
        providers=1_000,
        patients=100_000,
        patient_visits=500_000,
        prescriptions=250_000,
        patient_documents=25_000,
        tickets=50_000,
        ticket_messages=1_000_000,
        invoices=25_000,
        invoice_line_items=100_000,
        raw_events=5_000_000,
        comments=50_000,
        subscriptions=500,
        user_addresses=10_000,
        user_payment_methods=4_000,
        api_keys=5_000,
        sessions=15_000,
        audit_events=50_000,
    ),
}


def tier_params(name: TierName, *, scale: int = 1) -> TierParams:
    """Return tier row counts, optionally scaled for stress runs."""
    base = _TIERS[name]
    if scale == 1:
        return base
    return TierParams(
        organizations=base.organizations * scale,
        users=base.users * scale,
        employees=base.employees * scale,
        providers=base.providers * scale,
        patients=base.patients * scale,
        patient_visits=base.patient_visits * scale,
        prescriptions=base.prescriptions * scale,
        patient_documents=base.patient_documents * scale,
        tickets=base.tickets * scale,
        ticket_messages=base.ticket_messages * scale,
        invoices=base.invoices * scale,
        invoice_line_items=base.invoice_line_items * scale,
        raw_events=base.raw_events * scale,
        comments=base.comments * scale,
        subscriptions=base.subscriptions * scale,
        user_addresses=base.user_addresses * scale,
        user_payment_methods=base.user_payment_methods * scale,
        api_keys=base.api_keys * scale,
        sessions=base.sessions * scale,
        audit_events=base.audit_events * scale,
    )


def resolve_tier(name: str, *, scale: int = 1) -> TierParams:
    """Parse a tier name string and return scaled parameters."""
    tier = TierName(name)
    if tier is TierName.STRESS:
        return tier_params(TierName.DEMO, scale=max(scale, 10))
    return tier_params(tier, scale=scale)
