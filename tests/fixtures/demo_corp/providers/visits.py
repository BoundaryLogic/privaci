"""Patient visit row generators."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tests.fixtures.demo_corp.providers.messages import narrative_visit_notes
from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams

_REGIONS = ("us_east", "us_west", "us_central", "intl")


def generate_visit_rows(params: TierParams) -> dict[str, str]:
    """Generate SQL for list-partitioned patient visits."""
    rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.patient_visits + 1):
        patient_id = ((idx - 1) % params.patients) + 1
        provider_id = ((idx - 1) % params.providers) + 1
        region = _REGIONS[idx % len(_REGIONS)]
        visit_date = date(2024, 1, 1) + timedelta(days=idx % 365)
        notes = narrative_visit_notes(
            patient_name=f"Pat{patient_id} Patient{patient_id}",
            provider_name=f"Dr{provider_id} Provider{provider_id}",
            complaint="recurring headache",
            visit_date=visit_date.isoformat(),
        )
        rows.append(
            (
                patient_id,
                provider_id,
                visit_date,
                ("office", "telehealth", "emergency")[idx % 3],
                region,
                f"ICD-{idx % 100:03d}",
                "Patient reports symptoms",
                notes,
            )
        )

    return {
        "clinical.patient_visits": insert_sql(
            "clinical.patient_visits",
            [
                "patient_id",
                "provider_id",
                "visit_date",
                "visit_type",
                "region_code",
                "diagnosis_code",
                "chief_complaint",
                "visit_notes",
            ],
            rows,
        ),
    }
