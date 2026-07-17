"""Unit tests for assume_existing validation helpers."""

from __future__ import annotations

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.loader import SUPPORTED_VERSION
from privaci.config.models import Config
from privaci.schema.assume_existing import (
    AssumeExistingValidation,
    ColumnMismatch,
    binary_copy_columns_match,
    types_compatible,
    validation_failed_payload,
    validation_ok_payload,
)


def _catalog_with_users() -> CatalogResult:
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
        primary_key=("id",),
    )
    return CatalogResult(
        tables={"public.users": table},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=("public.users",)),)),
    )


def test_types_compatible_normalizes_whitespace() -> None:
    assert types_compatible("character varying(50)", "character varying(50)")
    assert types_compatible("TEXT", "text")
    assert not types_compatible("text", "character varying(50)")


def test_binary_copy_columns_match_requires_order() -> None:
    table = _catalog_with_users().tables["public.users"]
    matching = [("id", "integer"), ("email", "text")]
    reordered = [("email", "text"), ("id", "integer")]
    with_extra = [("id", "integer"), ("email", "text"), ("audit_at", "timestamp")]

    assert binary_copy_columns_match(table, matching)
    assert not binary_copy_columns_match(table, reordered)
    assert not binary_copy_columns_match(table, with_extra)


def test_validation_payloads_are_pii_free() -> None:
    validation = AssumeExistingValidation(
        tables_checked=1,
        mismatches=(
            ColumnMismatch(
                table_id="public.users",
                column_name="email",
                source_type="text",
                target_type="character varying(50)",
                reason="type_mismatch",
            ),
        ),
    )
    failed = validation_failed_payload(validation, passthrough_copy="auto")
    ok = validation_ok_payload(
        AssumeExistingValidation(tables_checked=1, mismatches=()),
        passthrough_copy="batch",
    )

    assert failed["passthrough_copy"] == "auto"
    assert failed["mismatches"][0]["column"] == "email"
    assert "john" not in str(failed).lower()
    assert ok == {"passthrough_copy": "batch", "tables_checked": 1}


def test_config_defaults_for_schema_mode_and_passthrough_copy() -> None:
    config = Config(version=SUPPORTED_VERSION)

    assert config.schema_mode == "replicate"
    assert config.passthrough_copy == "auto"
