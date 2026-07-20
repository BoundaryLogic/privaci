"""Unit tests for DEFAULT/CHECK function hoist into pre-data."""

from __future__ import annotations

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import (
    CatalogResult,
    CheckConstraintInfo,
    ColumnInfo,
    FunctionInfo,
    TableInfo,
)
from privaci.config.models import Config
from privaci.schema.function_hoist import functions_required_for_pre_data


def test_functions_required_for_pre_data_detects_default_call() -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="id",
                data_type="integer",
                not_null=True,
                default_expression="public.gen_token()",
            ),
        ),
    )
    function = FunctionInfo(
        schema_name="public",
        function_name="gen_token",
        identity_args="",
        create_sql="CREATE FUNCTION public.gen_token() RETURNS integer LANGUAGE sql "
        "AS $$ SELECT 1 $$",
        language="sql",
        is_elevated=False,
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
        functions=(function,),
    )
    config = Config(version="1.0")

    # Act
    required = functions_required_for_pre_data(catalog, config)

    # Assert
    assert [fn.identifier for fn in required] == [function.identifier]


def test_functions_required_for_pre_data_detects_check_call() -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(ColumnInfo(name="email", data_type="text", not_null=True),),
        check_constraints=(
            CheckConstraintInfo(
                name="users_email_ok",
                definition="CHECK (public.is_email(email))",
            ),
        ),
    )
    function = FunctionInfo(
        schema_name="public",
        function_name="is_email",
        identity_args="text",
        create_sql="CREATE FUNCTION ...",
        language="sql",
        is_elevated=False,
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
        functions=(function,),
    )

    # Act
    required = functions_required_for_pre_data(catalog, Config(version="1.0"))

    # Assert
    assert len(required) == 1
    assert required[0].function_name == "is_email"


def test_functions_required_for_pre_data_transitive_closure() -> None:
    # Arrange — DEFAULT calls A; A depends on B; B depends on C.
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="id",
                data_type="integer",
                not_null=True,
                default_expression="public.fn_a()",
            ),
        ),
    )
    fn_c = FunctionInfo(
        schema_name="public",
        function_name="fn_c",
        identity_args="",
        create_sql="CREATE FUNCTION public.fn_c() ...",
        language="sql",
        is_elevated=False,
    )
    fn_b = FunctionInfo(
        schema_name="public",
        function_name="fn_b",
        identity_args="",
        create_sql="CREATE FUNCTION public.fn_b() ...",
        language="sql",
        is_elevated=False,
        depends_on_functions=(fn_c.identifier,),
    )
    fn_a = FunctionInfo(
        schema_name="public",
        function_name="fn_a",
        identity_args="",
        create_sql="CREATE FUNCTION public.fn_a() ...",
        language="sql",
        is_elevated=False,
        depends_on_functions=(fn_b.identifier,),
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
        functions=(fn_a, fn_b, fn_c),
    )

    # Act
    required = functions_required_for_pre_data(catalog, Config(version="1.0"))

    # Assert — dependency order: C before B before A
    assert [fn.function_name for fn in required] == ["fn_c", "fn_b", "fn_a"]


def test_functions_required_hoists_when_replicate_functions_false() -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="token",
                data_type="text",
                not_null=True,
                default_expression="public.gen_token()",
            ),
        ),
    )
    function = FunctionInfo(
        schema_name="public",
        function_name="gen_token",
        identity_args="",
        create_sql="CREATE FUNCTION ...",
        language="sql",
        is_elevated=False,
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
        functions=(function,),
    )

    # Act
    required = functions_required_for_pre_data(
        catalog, Config(version="1.0", replicate_functions=False)
    )

    # Assert — DEFAULT deps still hoist; flag only gates remaining post-data fns
    assert [fn.identifier for fn in required] == [function.identifier]
