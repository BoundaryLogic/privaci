"""Require SpaCy when ``ner_mask`` is configured explicitly in YAML."""

from __future__ import annotations

from collections.abc import Iterator

from privaci.config.models import Config
from privaci.errors import ConfigError
from privaci.mask.ner import NER_MASK_REMEDIATION, spacy_available

_NER_ACTION = "ner_mask"


def iter_explicit_ner_columns(config: Config) -> Iterator[str]:
    """Yield ``tables.<t>.columns.<c>`` paths for explicit ``ner_mask`` actions."""
    for table_id, table in config.tables.items():
        for column_name, action in table.columns.items():
            if action.action == _NER_ACTION:
                yield f"tables.{table_id}.columns.{column_name}"


def validate_ner_mask_actions(config: Config) -> None:
    """Reject explicit ``ner_mask`` when SpaCy is unavailable (exit 3)."""
    paths = sorted(iter_explicit_ner_columns(config))
    if not paths:
        return
    if spacy_available():
        return
    raise ConfigError(
        "Validating ner_mask actions",
        cause=(
            "ner_mask requires SpaCy (en_core_web_sm) but it is not available on: "
            + ", ".join(paths)
        ),
        remediation=NER_MASK_REMEDIATION,
    )
