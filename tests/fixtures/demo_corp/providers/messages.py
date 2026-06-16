"""Narrative free-text generators for L2 NER bait."""

from __future__ import annotations


def narrative_ticket_body(
    *,
    patient_name: str,
    mrn: str,
    visit_date: str,
    author_name: str,
) -> str:
    """Build ticket message prose that mentions PHI-like tokens."""
    return (
        f"Hi team, patient {patient_name} (MRN {mrn}) called about their visit on "
        f"{visit_date}. They asked {author_name} to confirm the insurance update. "
        "Please review the chart and call them back today."
    )


def narrative_visit_notes(
    *,
    patient_name: str,
    provider_name: str,
    complaint: str,
    visit_date: str,
) -> str:
    """Build clinical visit notes with names and dates for NER testing."""
    return (
        f"On {visit_date}, {patient_name} was seen by {provider_name} for "
        f"{complaint}. Vitals stable. Plan: follow up in two weeks and review "
        "labs at the next appointment."
    )
