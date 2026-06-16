"""Merge YAML config with auto-detect findings."""

from __future__ import annotations

from privaci.autodetect.models import DetectionResult
from privaci.autodetect.scanner import scan_catalog
from privaci.catalog.models import CatalogResult, TableInfo
from privaci.config.actions import ColumnAction
from privaci.config.models import Config, TableConfig


def resolve_effective_table_config(
    table: TableInfo,
    config: Config,
    detection: DetectionResult,
) -> TableConfig:
    """Return the masking config for one table after auto-detect merge."""
    yaml_cfg = config.tables.get(table.identifier)
    if yaml_cfg is None:
        yaml_cfg = TableConfig()
    if not config.auto_detect:
        return yaml_cfg

    merged_columns = dict(yaml_cfg.columns)
    for column in table.columns:
        if column.name in merged_columns:
            continue
        finding = detection.finding_for(table.identifier, column.name)
        if finding is None or finding.action is None:
            continue
        merged_columns[column.name] = finding.action
    return TableConfig(
        strategy=yaml_cfg.strategy,
        columns=merged_columns,
        batch_size=yaml_cfg.batch_size,
        null_orphan_fks=yaml_cfg.null_orphan_fks,
    )


def uncovered_strict_columns(
    config: Config,
    detection: DetectionResult,
) -> tuple[str, ...]:
    """Return schema-qualified columns that fail strict auto-detect."""
    if not config.strict_autodetect:
        return ()
    uncovered: list[str] = []
    for finding in detection.findings:
        if finding.confidence not in {"high", "medium"}:
            continue
        if finding.matched_pattern is None:
            continue
        table_cfg = config.tables.get(finding.table_id)
        if table_cfg is not None and table_cfg.strategy == "exclude":
            continue
        if table_cfg is not None and finding.column_name in table_cfg.columns:
            continue
        uncovered.append(f"{finding.table_id}.{finding.column_name}")
    return tuple(sorted(uncovered))


def build_detection(config: Config, catalog: CatalogResult) -> DetectionResult:
    """Scan the catalog unless auto-detect is disabled."""
    return scan_catalog(catalog, config)


def effective_columns_for_table(
    table: TableInfo,
    config: Config,
    detection: DetectionResult,
) -> dict[str, ColumnAction]:
    """Return the merged per-column action map for one table."""
    return resolve_effective_table_config(table, config, detection).columns
