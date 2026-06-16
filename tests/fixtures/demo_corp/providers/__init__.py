"""Row generators for Demo Corp tables."""

from __future__ import annotations

from tests.fixtures.demo_corp.providers.events import generate_events
from tests.fixtures.demo_corp.providers.messages import (
    narrative_ticket_body,
    narrative_visit_notes,
)
from tests.fixtures.demo_corp.providers.orgs import generate_org_data
from tests.fixtures.demo_corp.providers.patients import generate_clinical_data
from tests.fixtures.demo_corp.providers.tickets import generate_ticket_data
from tests.fixtures.demo_corp.providers.users import generate_user_data
from tests.fixtures.demo_corp.providers.visits import generate_visit_rows

__all__ = [
    "generate_clinical_data",
    "generate_events",
    "generate_org_data",
    "generate_ticket_data",
    "generate_user_data",
    "generate_visit_rows",
    "narrative_ticket_body",
    "narrative_visit_notes",
]
