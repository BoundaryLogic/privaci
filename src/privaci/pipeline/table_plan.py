"""Per-table disposition planning for the masking pipeline."""

from __future__ import annotations

import logging
from enum import Enum

from privaci.catalog.models import TableInfo
from privaci.config.models import Config
from privaci.schema.table_policy import table_strategy
from privaci.state import TableCheckpoint, ensure_table_resumable
from privaci.state.models import CheckpointStatus

logger = logging.getLogger(__name__)

# Re-export for callers that historically imported strategy from table_plan.
__all__ = ["TableAction", "plan_table", "table_strategy"]


class TableAction(str, Enum):
    """What the streaming loop should do for one table."""

    SKIP_DONE = "skip_done"
    SKIP_STRATEGY = "skip_strategy"
    FINALIZE_EMPTY = "finalize_empty"
    STREAM = "stream"


def plan_table(
    table: TableInfo,
    config: Config,
    checkpoint: TableCheckpoint | None,
) -> TableAction:
    """Return the disposition for one table in the load plan.

    Args:
        table: Catalog metadata for the table.
        config: Mask-rules configuration.
        checkpoint: Resume checkpoint for the table, if any.

    Returns:
        The action the streaming loop should take.
    """
    strategy = table_strategy(table, config)
    if _should_stream(table, config):
        return _stream_action(table, checkpoint)
    if strategy in ("empty", "truncate"):
        if checkpoint is not None and checkpoint.status is CheckpointStatus.DONE:
            return TableAction.SKIP_DONE
        return TableAction.FINALIZE_EMPTY
    return TableAction.SKIP_STRATEGY


def _stream_action(
    table: TableInfo,
    checkpoint: TableCheckpoint | None,
) -> TableAction:
    if checkpoint is None:
        return TableAction.STREAM
    ensure_table_resumable(table.primary_key, checkpoint)
    if checkpoint.status is CheckpointStatus.FAILED:
        logger.warning(
            "Retrying %s after a failed checkpoint",
            table.identifier,
            extra={
                "event": "table.retry",
                "table": table.identifier,
                "rows_processed": checkpoint.rows_processed,
            },
        )
    if checkpoint.status is CheckpointStatus.DONE:
        return TableAction.SKIP_DONE
    return TableAction.STREAM


def _should_stream(table: TableInfo, config: Config) -> bool:
    if table.is_partitioned:
        return False
    return table_strategy(table, config) == "transform"
