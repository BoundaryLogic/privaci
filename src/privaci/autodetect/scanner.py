"""Catalog-wide PII column scanning."""

from __future__ import annotations

from privaci.autodetect.actions import action_for_column
from privaci.autodetect.freeform import score_freeform_confidence
from privaci.autodetect.matcher import match_column_name
from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.autodetect.patterns import PatternRule
from privaci.catalog.models import CatalogResult, ColumnInfo, TableInfo
from privaci.config.actions import ColumnAction
from privaci.config.models import Config, TableConfig


def scan_catalog(catalog: CatalogResult, config: Config) -> DetectionResult:
    """Inspect every column and return detection findings.

    Explicit YAML column entries always yield a finding so dry-run reflects
    what will be masked. Pattern-based detection runs only when
    ``config.auto_detect`` is enabled.
    """
    findings: list[DetectionFinding] = []
    for table_id, table in sorted(catalog.tables.items()):
        if _table_is_excluded(table_id, config):
            continue
        table_cfg = config.tables.get(table_id)
        for column in table.columns:
            findings.append(
                _inspect_column(table, column, table_cfg, config.auto_detect)
            )
    return DetectionResult(findings=tuple(findings))


def _table_is_excluded(table_id: str, config: Config) -> bool:
    table_cfg = config.tables.get(table_id)
    return table_cfg is not None and table_cfg.strategy == "exclude"


def _inspect_column(
    table: TableInfo,
    column: ColumnInfo,
    table_cfg: TableConfig | None,
    auto_detect: bool,
) -> DetectionFinding:
    explicit = table_cfg.columns.get(column.name) if table_cfg else None
    if explicit is not None:
        return _finding_from_config(table.identifier, column.name, explicit)

    if not auto_detect:
        return DetectionFinding(
            table_id=table.identifier,
            column_name=column.name,
            confidence="low",
            reasons=("auto-detect disabled",),
        )

    rule = match_column_name(column.name)
    if rule is None:
        return DetectionFinding(
            table_id=table.identifier,
            column_name=column.name,
            confidence="low",
            reasons=("no pattern match",),
        )
    return _finding_from_rule(table, column, rule)


def _finding_from_config(
    table_id: str,
    column_name: str,
    action: ColumnAction,
) -> DetectionFinding:
    provider = action.provider if action.action == "fake" else None
    return DetectionFinding(
        table_id=table_id,
        column_name=column_name,
        confidence="high",
        reasons=("explicit config",),
        action=action,
        provider=provider,
        source="config",
    )


def _finding_from_rule(
    table: TableInfo,
    column: ColumnInfo,
    rule: PatternRule,
) -> DetectionFinding:
    action = action_for_column(rule, column)
    if action is None:
        return _incompatible_rule_finding(table, column, rule)
    if rule.action == "ner_mask":
        return _ner_rule_finding(table, column, rule, action)
    return _matched_rule_finding(table, column, rule, action)


def _incompatible_rule_finding(
    table: TableInfo,
    column: ColumnInfo,
    rule: PatternRule,
) -> DetectionFinding:
    return DetectionFinding(
        table_id=table.identifier,
        column_name=column.name,
        confidence="low",
        reasons=(
            f"matched pattern {rule.rule_id}",
            f"action {rule.action} incompatible with type {column.data_type}",
        ),
        matched_pattern=rule.rule_id,
    )


def _ner_rule_finding(
    table: TableInfo,
    column: ColumnInfo,
    rule: PatternRule,
    action: ColumnAction,
) -> DetectionFinding:
    confidence, reasons = score_freeform_confidence(
        table_name=table.table_name,
        column=column,
    )
    merged = (f"matched pattern {rule.rule_id}",) + reasons
    effective_action = action if confidence == "high" else None
    return DetectionFinding(
        table_id=table.identifier,
        column_name=column.name,
        confidence=confidence,
        reasons=merged,
        action=effective_action,
        provider=None,
        matched_pattern=rule.rule_id,
    )


def _matched_rule_finding(
    table: TableInfo,
    column: ColumnInfo,
    rule: PatternRule,
    action: ColumnAction,
) -> DetectionFinding:
    provider = action.provider if action.action == "fake" else None
    return DetectionFinding(
        table_id=table.identifier,
        column_name=column.name,
        confidence="high",
        reasons=(f"matched pattern {rule.rule_id}",),
        action=action,
        provider=provider,
        matched_pattern=rule.rule_id,
    )
