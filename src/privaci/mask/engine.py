"""Per-table masking engine — pure (config, salt, row) → row."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from privaci.catalog.models import TableInfo
from privaci.cel.binding import annotations_for_when
from privaci.cel.sandbox import CompiledWhen, compile_when, evaluate_when
from privaci.config.models import TableConfig
from privaci.mask.column_masker import mask_column_value, unique_column_names
from privaci.mask.safe_log import safe_value_preview

if TYPE_CHECKING:
    from privaci.contracts.base import CellPostProcessor

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WhenEvalStats:
    """Per-column counters for conditional-skip rollup audits."""

    evaluated_rows: int = 0
    skipped_rows: int = 0


@dataclass(frozen=True, slots=True)
class ConditionalSkipAudit:
    """Value-free rollup for one guarded column that skipped at least one row."""

    column_name: str
    expression_hash: str
    skipped_rows: int
    evaluated_rows: int


class MaskingEngine:
    """Apply configured column actions to rows for one table.

    Stateless after construction except conditional-skip counters used for
    rollup audits. No I/O is performed during masking.

    Attributes:
        salt: Anonymization salt (never logged).
        table_id: Schema-qualified table identifier.
        table_info: Catalog metadata for uniqueness detection.
        table_config: Per-table masking configuration.
    """

    __slots__ = (
        "_cell_post_processor",
        "_null_columns",
        "_pseudonym_key",
        "_salt",
        "_table_config",
        "_table_id",
        "_table_info",
        "_unique_columns",
        "_when_programs",
        "_when_stats",
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
        null_columns: frozenset[str] | None = None,
    ) -> None:
        self._salt = salt
        self._pseudonym_key = pseudonym_key
        self._table_id = table_id
        self._table_info = table_info
        self._table_config = table_config
        self._cell_post_processor = cell_post_processor
        self._null_columns = null_columns or frozenset()
        unique_idx = tuple(idx.columns for idx in table_info.indexes if idx.is_unique)
        self._unique_columns = unique_column_names(
            primary_key=table_info.primary_key,
            unique_groups=table_info.unique_constraints,
            unique_index_columns=unique_idx,
        )
        self._when_programs, self._when_stats = _compile_when_guards(
            table_id, table_info, table_config
        )

    def __repr__(self) -> str:
        return f"MaskingEngine(table_id={self._table_id!r})"

    @property
    def uses_cell_post_processing(self) -> bool:
        """Return whether a commercial cell hook may mutate values after masking."""
        return self._cell_post_processor is not None

    @property
    def requires_row_mutation(self) -> bool:
        """Return True when binary whole-table COPY cannot preserve semantics."""
        return (
            self.uses_cell_post_processing
            or bool(self._null_columns)
            or bool(self._when_programs)
        )

    def mask_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Return a masked copy of ``row``.

        Columns without an explicit config action are passed through unchanged.
        Orphan FK columns configured for nulling are set to ``None``.
        Columns whose ``when`` evaluates false are left unchanged.
        """
        masked: dict[str, Any] = {}
        for column_name, value in row.items():
            if column_name in self._null_columns:
                masked[column_name] = None
                continue
            if not self._evaluate_when_guard(column_name, row):
                masked[column_name] = value
                continue
            masked[column_name] = self._mask_cell(column_name, value)
        return masked

    def drain_conditional_skip_audits(self) -> list[ConditionalSkipAudit]:
        """Return rollup payloads for columns that skipped at least one row."""
        events: list[ConditionalSkipAudit] = []
        for column_name, compiled in self._when_programs.items():
            stats = self._when_stats[column_name]
            if stats.skipped_rows <= 0:
                continue
            events.append(
                ConditionalSkipAudit(
                    column_name=column_name,
                    expression_hash=compiled.expression_hash,
                    skipped_rows=stats.skipped_rows,
                    evaluated_rows=stats.evaluated_rows,
                )
            )
        return events

    def _evaluate_when_guard(self, column_name: str, row: dict[str, Any]) -> bool:
        """Return whether masking should run; update skip counters."""
        compiled = self._when_programs.get(column_name)
        if compiled is None:
            return True
        stats = self._when_stats[column_name]
        stats.evaluated_rows += 1
        if evaluate_when(compiled, row):
            return True
        stats.skipped_rows += 1
        return False

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


def _compile_when_guards(
    table_id: str,
    table_info: TableInfo,
    table_config: TableConfig,
) -> tuple[dict[str, CompiledWhen], dict[str, WhenEvalStats]]:
    """Compile per-column ``when`` programs and zero skip counters."""
    programs: dict[str, CompiledWhen] = {}
    stats: dict[str, WhenEvalStats] = {}
    column_types = {col.name: col.data_type for col in table_info.columns}
    for column_name, action in table_config.columns.items():
        when = action.when
        if not isinstance(when, str) or not when.strip():
            continue
        path = f"tables.{table_id}.columns.{column_name}.when"
        annotations = annotations_for_when(
            when, column_path=path, column_types=column_types
        )
        programs[column_name] = compile_when(
            when, column_path=path, annotations=annotations
        )
        stats[column_name] = WhenEvalStats()
    return programs, stats
