"""Run state, checkpoints, and audit log in the ``_privaci`` schema.

Public surface for creating the state schema, recording run lifecycle,
advancing per-table checkpoints, and writing the audit log. See
``state-and-audit/spec.md`` and ADR-0004 for the design rationale.
"""

from __future__ import annotations

from privaci.state.audit import AuditWriter
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.state.ddl import STATE_SCHEMA_NAME, STATE_SCHEMA_VERSION
from privaci.state.fingerprints import (
    config_hash,
    generate_uuid7,
    salt_fingerprint,
    source_db_hash,
)
from privaci.state.models import (
    AuditLevel,
    CheckpointStatus,
    EventType,
    RunIdentity,
    RunStatus,
)
from privaci.state.resume import (
    TableCheckpoint,
    ensure_table_resumable,
    find_resumable_run,
    load_checkpoints,
    parse_checkpoint_cursor,
    reopen_resumable_run,
    require_resumable_run,
    resolve_resumable_run,
)
from privaci.state.runs import finish_run, start_run
from privaci.state.schema import ensure_state_schema

__all__ = [
    "STATE_SCHEMA_NAME",
    "STATE_SCHEMA_VERSION",
    "AuditLevel",
    "AuditWriter",
    "CheckpointStatus",
    "EventType",
    "RunIdentity",
    "RunStatus",
    "TableCheckpoint",
    "config_hash",
    "ensure_state_schema",
    "ensure_table_resumable",
    "find_resumable_run",
    "finish_run",
    "load_checkpoints",
    "parse_checkpoint_cursor",
    "reopen_resumable_run",
    "require_resumable_run",
    "resolve_resumable_run",
    "generate_uuid7",
    "mark_table_done",
    "salt_fingerprint",
    "source_db_hash",
    "start_run",
    "write_checkpoint",
]
