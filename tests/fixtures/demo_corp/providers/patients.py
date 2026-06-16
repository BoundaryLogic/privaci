"""Clinical patient and provider row generators."""

from __future__ import annotations

from datetime import date, timedelta

from tests.fixtures.demo_corp.seed import fixture_email, fixture_phone, fixture_ssn
from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams


def generate_clinical_data(params: TierParams) -> dict[str, str]:
    """Generate SQL for providers, patients, prescriptions, and documents."""
    provider_rows = [
        (
            f"1{idx:09d}",
            f"A{idx:08d}",
            f"Dr{idx}",
            f"Provider{idx}",
            fixture_email("provider", idx),
            ("cardiology", "pediatrics", "oncology", "neurology")[idx % 4],
            ((idx - 1) % params.organizations) + 1,
        )
        for idx in range(1, params.providers + 1)
    ]

    patient_rows = [
        (
            f"MRN{idx:08d}",
            f"Pat{idx}",
            f"Patient{idx}",
            f"Pat{idx} Patient{idx}",
            date(1950, 1, 1) + timedelta(days=idx * 7 % 25000),
            fixture_ssn(idx + 1000),
            fixture_phone(10_000 + idx),
            fixture_email("patient", idx),
            ((idx - 1) % params.providers) + 1,
            ((idx - 1) % params.organizations) + 1,
            f"INS{idx:09d}",
            f"GRP{(idx % 5) + 1}",
        )
        for idx in range(1, params.patients + 1)
    ]

    prescription_rows = [
        (
            ((idx - 1) % params.patients) + 1,
            ((idx - 1) % params.providers) + 1,
            f"Drug-{idx % 50}",
            f"{idx % 10 + 1}mg",
            idx % 5,
            date(2024, 1, 1) + timedelta(days=idx % 365),
        )
        for idx in range(1, params.prescriptions + 1)
    ]

    document_rows = [
        (
            ((idx - 1) % params.patients) + 1,
            fixture_email("provider", ((idx - 1) % params.providers) + 1),
            bytes(f"synthetic-doc-{idx}".encode()),
            fixture_email("user", ((idx - 1) % params.users) + 1),
        )
        for idx in range(1, params.patient_documents + 1)
    ]

    return {
        "clinical.providers": insert_sql(
            "clinical.providers",
            [
                "npi",
                "dea_number",
                "first_name",
                "last_name",
                "email",
                "specialty",
                "org_id",
            ],
            provider_rows,
        ),
        "clinical.patients": insert_sql(
            "clinical.patients",
            [
                "mrn",
                "first_name",
                "last_name",
                "full_name",
                "dob",
                "ssn",
                "phone",
                "email",
                "primary_provider_id",
                "org_id",
                "insurance_member_id",
                "insurance_group",
            ],
            patient_rows,
        ),
        "clinical.prescriptions": insert_sql(
            "clinical.prescriptions",
            [
                "patient_id",
                "provider_id",
                "drug_name",
                "dosage",
                "refills",
                "prescribed_at",
            ],
            prescription_rows,
        ),
        "clinical.patient_documents": insert_sql(
            "clinical.patient_documents",
            [
                "patient_id",
                "referring_provider_email",
                "document_blob",
                "uploaded_by_user_email",
            ],
            document_rows,
        ),
    }
