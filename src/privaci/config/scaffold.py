"""Build starter mask-rules.yaml content from a source catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from privaci.autodetect import scan_catalog
from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.catalog.models import CatalogResult, TableInfo
from privaci.catalog.partitions import is_partition_child
from privaci.config.actions import ColumnAction
from privaci.config.loader import SUPPORTED_VERSION
from privaci.config.models import Config, TableConfig
from privaci.secrets.types import SecretStr


@dataclass(frozen=True, slots=True)
class ScaffoldResult:
    """Output of :func:`build_scaffold_config`."""

    config: Config
    detection: DetectionResult
    review_findings: tuple[DetectionFinding, ...]


def build_scaffold_config(
    catalog: CatalogResult,
    *,
    schema_filter: frozenset[str] | None = None,
) -> ScaffoldResult:
    """Create a starter :class:`Config` from introspection and auto-detect.

    High-confidence findings become explicit column actions. Tables without a
    primary key default to ``exclude``. Partition children are omitted.

    Args:
        catalog: Introspected source schema.
        schema_filter: When set, only tables in these schemas are included.

    Returns:
        Scaffolded config, full detection pass, and medium-confidence review items.
    """
    skeleton = Config(
        version=SUPPORTED_VERSION,
        global_salt=SecretStr("${ANONYMIZATION_SALT}"),
        on_existing_data="fail",
        auto_detect=True,
        strict_autodetect=False,
    )
    baseline = scan_catalog(catalog, skeleton)
    tables = _tables_from_catalog(catalog, baseline, schema_filter=schema_filter)
    config = skeleton.model_copy(update={"tables": tables})
    detection = scan_catalog(catalog, config)
    review = tuple(
        finding
        for finding in detection.findings
        if finding.confidence == "medium" and finding.matched_pattern is not None
    )
    return ScaffoldResult(config=config, detection=detection, review_findings=review)


def _tables_from_catalog(
    catalog: CatalogResult,
    detection: DetectionResult,
    *,
    schema_filter: frozenset[str] | None,
) -> dict[str, TableConfig]:
    tables: dict[str, TableConfig] = {}
    for table_id in sorted(catalog.tables):
        table = catalog.tables[table_id]
        if is_partition_child(table):
            continue
        if schema_filter is not None and table.schema_name not in schema_filter:
            continue
        strategy: Literal["transform", "exclude"] = (
            "exclude" if not table.primary_key else "transform"
        )
        columns = (
            _high_confidence_columns(table, detection)
            if strategy == "transform"
            else {}
        )
        tables[table_id] = TableConfig(strategy=strategy, columns=columns)
    return tables


def _high_confidence_columns(
    table: TableInfo,
    detection: DetectionResult,
) -> dict[str, ColumnAction]:
    columns: dict[str, ColumnAction] = {}
    for finding in detection.by_table(table.identifier):
        if finding.confidence != "high" or finding.action is None:
            continue
        columns[finding.column_name] = finding.action
    return columns
