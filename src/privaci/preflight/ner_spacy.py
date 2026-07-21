"""Preflight gate: effective ``ner_mask`` (including auto-detect) needs SpaCy."""

from __future__ import annotations

from collections.abc import Iterator

from privaci.autodetect.models import DetectionResult
from privaci.autodetect.resolve import resolve_effective_table_config
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.mask.ner import NER_MASK_REMEDIATION, spacy_available

_NER_ACTION = "ner_mask"


def iter_effective_ner_columns(
    config: Config,
    catalog: CatalogResult,
    detection: DetectionResult,
) -> Iterator[str]:
    """Yield schema-qualified columns whose effective action is ``ner_mask``."""
    for table in catalog.tables.values():
        if table.identifier not in config.tables and not config.auto_detect:
            continue
        effective = resolve_effective_table_config(table, config, detection)
        for column_name, action in effective.columns.items():
            if action.action == _NER_ACTION:
                yield f"{table.identifier}.{column_name}"


def verify_ner_mask_spacy(
    config: Config,
    catalog: CatalogResult,
    detection: DetectionResult,
) -> None:
    """Reject effective ``ner_mask`` (including auto-detect) without SpaCy.

    Raises:
        PreflightError: Exit **2** when SpaCy is unavailable for any effective
            ``ner_mask`` column.
    """
    paths = sorted(iter_effective_ner_columns(config, catalog, detection))
    if not paths:
        return
    if spacy_available():
        return
    raise PreflightError(
        "Validating ner_mask SpaCy prerequisite",
        cause=(
            "ner_mask requires SpaCy (en_core_web_sm) but it is not available for: "
            + ", ".join(paths)
        ),
        remediation=NER_MASK_REMEDIATION,
    )
