"""Unit tests for post-data DDL helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import (
    CatalogResult,
    FunctionInfo,
    IndexInfo,
    TableInfo,
    TriggerInfo,
)
from privaci.config.models import Config, TableConfig
from privaci.schema.post_data import (
    apply_post_data_ddl,
    trigger_function_replicable,
    trigger_should_replicate,
)


def _catalog_with_trigger(*, elevated_fn: bool = False) -> CatalogResult:
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(),
        indexes=(
            IndexInfo(
                name="users_email_idx",
                is_unique=False,
                definition='CREATE INDEX "users_email_idx" ON public.users (email)',
                columns=("email",),
            ),
        ),
    )
    function = FunctionInfo(
        schema_name="public",
        function_name="users_audit",
        identity_args="",
        create_sql="CREATE FUNCTION public.users_audit() ...",
        language="plpgsql",
        is_elevated=elevated_fn,
    )
    trigger = TriggerInfo(
        schema_name="public",
        table_name="users",
        trigger_name="users_audit",
        create_sql="CREATE TRIGGER users_audit ...",
        function_identity=function.identifier,
    )
    return CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
        functions=(function,),
        triggers=(trigger,),
    )


def test_trigger_should_replicate_default() -> None:
    catalog = _catalog_with_trigger()
    config = Config(version="1.0", tables={"public.users": TableConfig()})

    assert trigger_should_replicate(catalog.triggers[0], catalog, config) is True


def test_trigger_skipped_when_function_elevated_without_disposition() -> None:
    catalog = _catalog_with_trigger(elevated_fn=True)
    config = Config(version="1.0", tables={"public.users": TableConfig()})

    assert trigger_function_replicable(catalog.triggers[0], catalog, config) is False
    assert trigger_should_replicate(catalog.triggers[0], catalog, config) is False


def test_trigger_skipped_when_flag_disabled() -> None:
    catalog = _catalog_with_trigger()
    config = Config(
        version="1.0",
        replicate_triggers=False,
        tables={"public.users": TableConfig()},
    )

    assert trigger_should_replicate(catalog.triggers[0], catalog, config) is False


@pytest.mark.asyncio
async def test_apply_post_data_noop_under_assume_existing() -> None:
    catalog = _catalog_with_trigger()
    config = Config(version="1.0", schema_mode="assume_existing")
    conn = AsyncMock()

    created, refreshed = await apply_post_data_ddl(conn, catalog, config)

    assert created == ()
    assert refreshed == ()
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_apply_post_data_creates_nonunique_index_and_trigger(
    mocker: pytest.MockFixture,
) -> None:
    catalog = _catalog_with_trigger()
    config = Config(
        version="1.0",
        replicate_all_indexes=True,
        replicate_views=False,
        replicate_functions=True,
        tables={"public.users": TableConfig()},
    )
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    mocker.patch(
        "privaci.schema.post_data.replicate_functions_and_views",
        new=AsyncMock(return_value=()),
    )
    mocker.patch(
        "privaci.schema.post_data.refresh_materialized_views",
        new=AsyncMock(return_value=()),
    )

    created, refreshed = await apply_post_data_ddl(conn, catalog, config)

    assert refreshed == ()
    kinds = {obj.kind for obj in created}
    assert "index" in kinds
    assert "trigger" in kinds
    index = next(obj for obj in created if obj.kind == "index")
    assert index.object_name == "users_email_idx"
    trigger = next(obj for obj in created if obj.kind == "trigger")
    assert trigger.object_name == "users"
    assert trigger.payload_object_name == "users_audit"
