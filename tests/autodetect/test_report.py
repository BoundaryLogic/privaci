"""Tests for markdown detection reports."""

from __future__ import annotations

from pathlib import Path

from privaci.autodetect import scan_catalog, write_detection_report
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.models import Config
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


def test_write_detection_report_creates_markdown(tmp_path: Path) -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(ColumnInfo(name="email", data_type="text", not_null=True),),
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=(table.identifier,)),)),
    )
    config = Config(version=SUPPORTED_CONFIG_VERSION)
    detection = scan_catalog(catalog, config)
    report_path = tmp_path / "report.md"

    # Act
    write_detection_report(
        report_path,
        catalog=catalog,
        detection=detection,
        config=config,
    )

    # Assert
    content = report_path.read_text(encoding="utf-8")
    assert "# PrivaCI auto-detect report" in content
    assert "public.users" in content
    assert "email" in content
