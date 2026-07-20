"""Capability and catalog validation for column ``when:`` CEL guards."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

from privaci.cel.binding import annotations_for_when
from privaci.cel.sandbox import compile_when
from privaci.config.actions import ColumnAction
from privaci.config.models import Config
from privaci.contracts.plugins import load_plugins
from privaci.errors import LicenseError, PreflightError

if TYPE_CHECKING:
    from privaci.catalog.models import CatalogResult

CONDITIONAL_MASKING_CAPABILITY = "conditional_masking"

_WHEN_DOCS = "docs/configuration.md#conditional-masking-when"


def iter_when_columns(config: Config) -> Iterator[tuple[str, str, str]]:
    """Yield ``(table_id, column, expression)`` for every non-empty ``when``."""
    for table_id, table in config.tables.items():
        for column_name, action in table.columns.items():
            when = action.when
            if isinstance(when, str) and when.strip():
                yield table_id, column_name, when


def table_has_when(table_config_columns: Mapping[str, ColumnAction]) -> bool:
    """Return True when any column action in the map has a non-empty ``when``."""
    for action in table_config_columns.values():
        when = action.when
        if isinstance(when, str) and when.strip():
            return True
    return False


def validate_conditional_masking(config: Config) -> None:
    """Enforce capability + CEL syntax at config load (no catalog).

    Raises:
        LicenseError: When ``conditional_masking`` is not granted (exit 5).
        ConfigError: When any ``when`` fails syntax/size/policy compile (exit 3).
    """
    when_columns = list(iter_when_columns(config))
    if not when_columns:
        return

    status = load_plugins().license_validator.validate()
    if CONDITIONAL_MASKING_CAPABILITY not in status.capabilities:
        paths = sorted(
            f"tables.{table}.columns.{column}" for table, column, _ in when_columns
        )
        raise LicenseError(
            "Validating conditional masking (when:)",
            cause=(
                "Column when: guards require the 'conditional_masking' capability "
                "on: " + ", ".join(paths)
            ),
            remediation=(
                "Install a plugin package whose LicenseValidator grants the "
                f"'conditional_masking' capability, or remove when: from "
                f"mask-rules.yaml. See {_WHEN_DOCS}."
            ),
        )

    for table_id, column, expression in when_columns:
        path = f"tables.{table_id}.columns.{column}.when"
        compile_when(expression, column_path=path, annotations=None)


def validate_when_against_catalog(config: Config, catalog: CatalogResult) -> None:
    """Type-check every ``when`` against the owning table's columns.

    Raises:
        ConfigError: Unsupported types or unknown column references (exit 3).
    """
    for table_id, column, expression in iter_when_columns(config):
        path = f"tables.{table_id}.columns.{column}.when"
        table = catalog.tables.get(table_id)
        if table is None:
            continue
        column_types = {col.name: col.data_type for col in table.columns}
        annotations = annotations_for_when(
            expression, column_path=path, column_types=column_types
        )
        compile_when(expression, column_path=path, annotations=annotations)


def assert_require_binary_allows_when(config: Config) -> None:
    """Fail when ``require_binary`` collides with any ``when`` guard."""
    if config.passthrough_copy != "require_binary":
        return
    offenders = sorted({table_id for table_id, _, _ in iter_when_columns(config)})
    if not offenders:
        return
    raise PreflightError(
        "Checking passthrough_copy: require_binary eligibility",
        cause=("when: guards require the batch/row path for: " + ", ".join(offenders)),
        remediation=(
            "Set passthrough_copy: auto or batch when using when: on any column."
        ),
    )
