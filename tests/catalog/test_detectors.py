"""Unit tests for catalog pattern detectors."""

from __future__ import annotations

from privaci.catalog.detectors import (
    detect_implied_fks,
    detect_polymorphic_fks,
    mark_self_cycles,
)
from privaci.catalog.models import ColumnInfo, ForeignKeyInfo, TableInfo, table_id


def _unique_email_table(schema: str, name: str) -> TableInfo:
    return TableInfo(
        schema_name=schema,
        table_name=name,
        columns=(ColumnInfo("email", "text", True),),
        unique_constraints=(("email",),),
    )


def test_mark_self_cycles_flags_self_referential_table() -> None:
    # Arrange
    employees = TableInfo(
        schema_name="public",
        table_name="employees",
        columns=(),
        foreign_keys=(
            ForeignKeyInfo(
                name="employees_manager_fk",
                source_columns=("manager_id",),
                referenced_schema="public",
                referenced_table="employees",
                referenced_columns=("id",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=True,
                initially_deferred=True,
            ),
        ),
    )
    tables = {table_id("public", "employees"): employees}

    # Act
    updated = mark_self_cycles(tables)

    # Assert
    assert updated["public.employees"].self_cycle is True


def test_detect_polymorphic_fks_warns_on_commentable_pair() -> None:
    # Arrange
    comments = TableInfo(
        schema_name="public",
        table_name="comments",
        columns=(
            ColumnInfo("commentable_type", "text", True),
            ColumnInfo("commentable_id", "bigint", True),
        ),
    )
    tables = {table_id("public", "comments"): comments}

    # Act
    warnings = detect_polymorphic_fks(tables)

    # Assert
    assert len(warnings) == 1
    assert warnings[0].code == "polymorphic_fk_warning"
    assert warnings[0].table_id == "public.comments"


def test_detect_implied_fks_flags_soft_email_reference() -> None:
    # Arrange
    providers = _unique_email_table("clinical", "providers")
    documents = TableInfo(
        schema_name="clinical",
        table_name="patient_documents",
        columns=(ColumnInfo("referring_provider_email", "text", False),),
    )
    tables = {
        table_id("clinical", "providers"): providers,
        table_id("clinical", "patient_documents"): documents,
    }

    # Act
    warnings = detect_implied_fks(tables)

    # Assert
    assert len(warnings) == 1
    assert warnings[0].code == "implied_fk_warning"
    assert warnings[0].table_id == "clinical.patient_documents"
    assert "seed_alias: clinical.providers.email" in warnings[0].message


def test_detect_implied_fks_disambiguates_target_by_prefix() -> None:
    # Arrange
    providers = _unique_email_table("clinical", "providers")
    users = _unique_email_table("public", "users")
    documents = TableInfo(
        schema_name="clinical",
        table_name="patient_documents",
        columns=(
            ColumnInfo("referring_provider_email", "text", False),
            ColumnInfo("uploaded_by_user_email", "text", False),
        ),
    )
    tables = {
        table_id("clinical", "providers"): providers,
        table_id("public", "users"): users,
        table_id("clinical", "patient_documents"): documents,
    }

    # Act
    warnings = detect_implied_fks(tables)

    # Assert
    by_message = {w.message for w in warnings}
    assert any("clinical.providers.email" in m for m in by_message)
    assert any("public.users.email" in m for m in by_message)
    assert len(warnings) == 2


def test_detect_implied_fks_skips_when_no_unique_target() -> None:
    # Arrange
    documents = TableInfo(
        schema_name="clinical",
        table_name="patient_documents",
        columns=(ColumnInfo("referring_provider_email", "text", False),),
    )
    tables = {table_id("clinical", "patient_documents"): documents}

    # Act
    warnings = detect_implied_fks(tables)

    # Assert
    assert warnings == ()


def test_detect_implied_fks_respects_ignore_list() -> None:
    # Arrange
    providers = _unique_email_table("clinical", "providers")
    documents = TableInfo(
        schema_name="clinical",
        table_name="patient_documents",
        columns=(ColumnInfo("referring_provider_email", "text", False),),
    )
    tables = {
        table_id("clinical", "providers"): providers,
        table_id("clinical", "patient_documents"): documents,
    }
    ignore = frozenset({"clinical.patient_documents.referring_provider_email"})

    # Act
    warnings = detect_implied_fks(tables, ignore=ignore)

    # Assert
    assert warnings == ()


def test_detect_implied_fks_skips_existing_catalog_fk() -> None:
    # Arrange
    providers = _unique_email_table("clinical", "providers")
    documents = TableInfo(
        schema_name="clinical",
        table_name="patient_documents",
        columns=(ColumnInfo("referring_provider_email", "text", False),),
        foreign_keys=(
            ForeignKeyInfo(
                name="docs_provider_email_fk",
                source_columns=("referring_provider_email",),
                referenced_schema="clinical",
                referenced_table="providers",
                referenced_columns=("email",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=False,
                initially_deferred=False,
            ),
        ),
    )
    tables = {
        table_id("clinical", "providers"): providers,
        table_id("clinical", "patient_documents"): documents,
    }

    # Act
    warnings = detect_implied_fks(tables)

    # Assert
    assert warnings == ()


def test_detect_implied_fks_matches_mrn_suffix() -> None:
    # Arrange
    patients = TableInfo(
        schema_name="clinical",
        table_name="patients",
        columns=(ColumnInfo("mrn", "text", True),),
        unique_constraints=(("mrn",),),
    )
    referrals = TableInfo(
        schema_name="clinical",
        table_name="referrals",
        columns=(ColumnInfo("source_patient_mrn", "text", False),),
    )
    tables = {
        table_id("clinical", "patients"): patients,
        table_id("clinical", "referrals"): referrals,
    }

    # Act
    warnings = detect_implied_fks(tables)

    # Assert
    assert len(warnings) == 1
    assert "seed_alias: clinical.patients.mrn" in warnings[0].message
