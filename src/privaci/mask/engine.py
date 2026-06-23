"""Per-table masking engine — pure (config, salt, row) → row."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from privaci.catalog.models import TableInfo
from privaci.config.models import TableConfig
from privaci.mask.column_masker import mask_column_value, unique_column_names
from privaci.mask.safe_log import safe_value_preview

if TYPE_CHECKING:
    from privaci.contracts.base import CellPostProcessor

logger = logging.getLogger(__name__)


class MaskingEngine:
    """Apply configured column actions to rows for one table.

    Stateless after construction: all inputs are captured in the constructor.
    No I/O is performed during masking.

    Attributes:
        salt: Anonymization salt (never logged).
        table_id: Schema-qualified table identifier.
        table_info: Catalog metadata for uniqueness detection.
        table_config: Per-table masking configuration.

    Example:
        >>> engine = MaskingEngine("secret-salt", "public.users", info, cfg)
        >>> masked = engine.mask_row({"email": "a@b.com", "id": 1})
    """

    __slots__ = (
        "_cell_post_processor",
        "_pseudonym_key",
        "_salt",
        "_table_config",
        "_table_id",
        "_table_info",
        "_unique_columns",
    )

    def __init__(
        self,
        salt: str,
        table_id: str,
        table_info: TableInfo,
        table_config: TableConfig,
        *,
        cell_post_processor: CellPostProcessor | None = None,
        pseudonym_key: str | None = None,
    ) -> None:
        self._salt = salt
        self._pseudonym_key = pseudonym_key
        self._table_id = table_id
        self._table_info = table_info
        self._table_config = table_config
        self._cell_post_processor = cell_post_processor
        # Uniqueness is fixed per table, so resolve it once here for O(1) lookup
        # in the per-cell hot path instead of re-scanning tuples for every row.
        unique_idx = tuple(idx.columns for idx in table_info.indexes if idx.is_unique)
        self._unique_columns = unique_column_names(
            primary_key=table_info.primary_key,
            unique_groups=table_info.unique_constraints,
            unique_index_columns=unique_idx,
        )

    def __repr__(self) -> str:
        return f"MaskingEngine(table_id={self._table_id!r})"

    @property
    def uses_cell_post_processing(self) -> bool:
        """Return whether a commercial cell hook may mutate values after masking."""
        return self._cell_post_processor is not None

    def mask_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Return a masked copy of ``row``.

        Columns without an explicit config action are passed through unchanged.
        """
        masked: dict[str, Any] = {}
        for column_name, value in row.items():
            masked[column_name] = self._mask_cell(column_name, value)
        return masked

    def _mask_cell(self, column_name: str, value: Any) -> Any:
        action = self._table_config.columns.get(column_name)
        column_path = f"{self._table_id}.{column_name}"
        is_unique = column_name in self._unique_columns
        if action is None:
            result = value
        else:
            try:
                result = mask_column_value(
                    value,
                    action,
                    salt=self._salt,
                    column_path=column_path,
                    is_unique=is_unique,
                    pseudonym_key=self._pseudonym_key,
                )
            except Exception:
                logger.debug(
                    "Mask failed for %s (preview=%s)",
                    column_path,
                    safe_value_preview(value),
                )
                raise
        if self._cell_post_processor is not None:
            result = self._cell_post_processor(self._table_id, column_name, result)
        return result
