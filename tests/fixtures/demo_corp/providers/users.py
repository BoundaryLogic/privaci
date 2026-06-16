"""User, address, payment, and employee row generators."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from tests.fixtures.demo_corp.seed import fixture_email, fixture_phone, fixture_ssn
from tests.fixtures.demo_corp.sql_writer import insert_sql
from tests.fixtures.demo_corp.tiers import TierParams


def generate_user_data(params: TierParams) -> dict[str, str]:
    """Generate SQL for users and related public-side PII tables."""
    user_rows: list[tuple[Any, ...]] = []
    for idx in range(1, params.users + 1):
        user_rows.append(
            (
                fixture_email("user", idx),
                fixture_phone(idx),
                f"First{idx}",
                f"Last{idx}",
                date(1980, 1, 1) + timedelta(days=idx * 11 % 7000),
                fixture_ssn(idx),
                f"hash-{idx:08x}",
                "admin" if idx % 50 == 0 else "user",
                ((idx - 1) % params.organizations) + 1,
                ((idx - 1) % 10) + 1 if idx > 10 else None,
                f"10.0.{idx // 256}.{idx % 256}",
            )
        )

    address_rows = [
        (
            idx,
            f"{idx} Main St",
            "Springfield",
            "IL",
            f"{60000 + idx}",
            "US",
        )
        for idx in range(1, min(params.user_addresses, params.users) + 1)
    ]

    payment_rows = [
        (
            idx,
            f"4111-1111-1111-{idx % 10000:04d}",
            f"{idx % 1000:03d}",
            (idx % 12) + 1,
            2026 + (idx % 3),
            f"Card Holder {idx}",
        )
        for idx in range(1, min(params.user_payment_methods, params.users) + 1)
    ]

    employee_rows = [
        (
            ((idx - 1) % params.organizations) + 1,
            ((idx - 1) % max(1, idx - 1)) + 1 if idx > 1 else None,
            f"Employee {idx}",
            fixture_ssn(idx + 10_000),
            date(1975, 1, 1) + timedelta(days=idx * 13 % 9000),
            date(2015, 1, 1) + timedelta(days=idx % 3000),
            50_000 + (idx * 100),
            f"1{idx:09d}" if idx % 5 == 0 else None,
        )
        for idx in range(1, params.employees + 1)
    ]

    session_rows = [
        (
            ((idx - 1) % params.users) + 1,
            UUID(int=idx),
            f"10.1.{idx // 256}.{idx % 256}",
            f"Mozilla/5.0 fixture/{idx}",
            None,
        )
        for idx in range(1, params.sessions + 1)
    ]

    api_key_rows = [
        (
            ((idx - 1) % params.users) + 1,
            f"keyhash-{idx:016x}",
            None,
            f"10.2.{idx // 256}.{idx % 256}",
            ["read", "write"] if idx % 2 == 0 else ["read"],
        )
        for idx in range(1, params.api_keys + 1)
    ]

    return {
        "public.users": insert_sql(
            "public.users",
            [
                "email",
                "phone",
                "first_name",
                "last_name",
                "dob",
                "ssn",
                "password_hash",
                "role",
                "org_id",
                "manager_id",
                "last_login_ip",
            ],
            user_rows,
        ),
        "public.user_addresses": insert_sql(
            "public.user_addresses",
            ["user_id", "street", "city", "state", "postcode", "country"],
            address_rows,
        ),
        "public.user_payment_methods": insert_sql(
            "public.user_payment_methods",
            [
                "user_id",
                "card_number",
                "cvv",
                "expiry_month",
                "expiry_year",
                "cardholder_name",
            ],
            payment_rows,
        ),
        "public.employees": insert_sql(
            "public.employees",
            [
                "org_id",
                "manager_id",
                "full_name",
                "ssn",
                "dob",
                "hire_date",
                "salary",
                "npi",
            ],
            employee_rows,
        ),
        "auth.sessions": insert_sql(
            "auth.sessions",
            ["user_id", "token", "ip_address", "user_agent", "expires_at"],
            session_rows,
        ),
        "auth.api_keys": insert_sql(
            "auth.api_keys",
            ["user_id", "key_hash", "last_used_at", "last_used_ip", "scopes"],
            api_key_rows,
        ),
    }
