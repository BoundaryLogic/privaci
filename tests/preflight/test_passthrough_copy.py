"""Unit tests for passthrough_copy eligibility helpers."""

from __future__ import annotations

import pytest

from privaci.autodetect.models import DetectionResult
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.loader import SUPPORTED_VERSION
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError
from privaci.preflight.passthrough_copy import verify_passthrough_copy_policy
from privaci.stream.passthrough_eligibility import (
    is_binary_copy_eligible,
    table_is_passthrough_candidate,
)


def _users_catalog() -> CatalogResult:
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


def test_table_is_passthrough_candidate_default() -> None:
    table = _users_catalog().tables["public.users"]
    assert table_is_passthrough_candidate(table, TableConfig())


@pytest.mark.asyncio
async def test_batch_policy_never_queries_binary_eligibility(
    mocker: pytest.MockFixture,
) -> None:
    table = _users_catalog().tables["public.users"]
    conn = mocker.AsyncMock()
    config = Config(version=SUPPORTED_VERSION, passthrough_copy="batch")

    eligible = await is_binary_copy_eligible(
        conn,
        table,
        TableConfig(),
        config,
        last_pk_value=None,
    )

    assert not eligible
    conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_require_binary_fails_when_order_mismatches(
    mocker: pytest.MockFixture,
) -> None:
    catalog = _users_catalog()
    config = Config(version=SUPPORTED_VERSION, passthrough_copy="require_binary")
    mocker.patch(
        "privaci.preflight.passthrough_copy.fetch_target_columns",
        new=mocker.AsyncMock(
            return_value=[("email", "text"), ("id", "integer")],
        ),
    )

    with pytest.raises(PreflightError, match="binary-COPY eligible"):
        await verify_passthrough_copy_policy(
            mocker.Mock(),
            catalog,
            config,
            DetectionResult(findings=()),
        )
