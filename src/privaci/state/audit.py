"""Audit-log writer for ``_privaci.audit_log``.

The audit log is on by default. When disabled via ``audit_log: false`` in
config or ``--no-audit-table`` on the CLI, the writer becomes a no-op while the
run row in ``_privaci.runs`` is still populated (resumability is unaffected).

Audit entries reference columns by name and counts only — never PII values.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg

from privaci.errors import StateError
from privaci.state.fingerprints import generate_uuid7
from privaci.state.models import AuditLevel, EventType

_INSERT_AUDIT_SQL = """
INSERT INTO _privaci.audit_log (
    audit_id, run_id, level, event_type,
    schema_name, table_name, column_name, payload
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
"""

_MARK_REFRESHED_SQL = """
UPDATE _privaci.audit_log AS a
SET payload = a.payload || '{"refreshed": true}'::jsonb
FROM unnest($2::text[], $3::text[]) AS t(schema_name, table_name)
WHERE a.run_id = $1
  AND a.event_type = 'definition_only_object'
  AND a.schema_name = t.schema_name
  AND a.table_name = t.table_name
"""


class AuditWriter:
    """Writes audit events for one run, honoring the opt-out switch.

    Attributes:
        run_id: The run these events belong to.
        enabled: When False, :meth:`write` is a no-op.

    Example:
        >>> writer = AuditWriter(run_id, enabled=config.audit_log)
        >>> await writer.write(conn, EventType.COLUMN_MASKED,
        ...     table_name="users", column_name="email",
        ...     payload={"action": "fake", "rows_affected": 100})
    """

    __slots__ = ("enabled", "run_id")

    def __init__(self, run_id: uuid.UUID, *, enabled: bool) -> None:
        self.run_id = run_id
        self.enabled = enabled

    def __repr__(self) -> str:
        return f"AuditWriter(run_id={self.run_id!s}, enabled={self.enabled})"

    async def write(
        self,
        conn: asyncpg.Connection,
        event_type: EventType,
        *,
        level: AuditLevel = AuditLevel.INFO,
        schema_name: str | None = None,
        table_name: str | None = None,
        column_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Write one audit event, or do nothing when disabled.

        Raises:
            StateError: If the audit row cannot be written.
        """
        if not self.enabled:
            return
        await _insert_audit_row(
            conn,
            self.run_id,
            event_type,
            level=level,
            schema_name=schema_name,
            table_name=table_name,
            column_name=column_name,
            payload=payload,
        )

    async def mark_definition_only_refreshed(
        self,
        conn: asyncpg.Connection,
        objects: tuple[tuple[str, str], ...],
    ) -> None:
        """Set ``payload.refreshed=true`` on matching definition_only audit rows.

        Args:
            conn: Target connection with ``_privaci.audit_log``.
            objects: ``(schema_name, table_name)`` pairs matching the create-time
                audit rows. Matching is schema-qualified to avoid cross-schema
                collisions on identical bare names.
        """
        if not self.enabled or not objects:
            return
        schemas = [schema for schema, _ in objects]
        names = [name for _, name in objects]
        try:
            await conn.execute(_MARK_REFRESHED_SQL, self.run_id, schemas, names)
        except asyncpg.PostgresError as exc:
            raise StateError(
                "Updating definition_only_object refresh status",
                cause="The audit refresh flag could not be updated.",
                remediation=(
                    "Ensure the _privaci schema exists, or disable the audit "
                    "log with --no-audit-table."
                ),
            ) from exc


async def _insert_audit_row(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    event_type: EventType,
    *,
    level: AuditLevel,
    schema_name: str | None,
    table_name: str | None,
    column_name: str | None,
    payload: dict[str, Any] | None,
) -> None:
    event_value = event_type.value
    body = json.dumps(payload if payload is not None else {})
    try:
        await conn.execute(
            _INSERT_AUDIT_SQL,
            generate_uuid7(),
            run_id,
            level.value,
            event_value,
            schema_name,
            table_name,
            column_name,
            body,
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Writing an audit-log entry",
            cause="The audit row could not be written.",
            remediation=(
                "Ensure the _privaci schema exists, or disable the audit "
                "log with --no-audit-table."
            ),
        ) from exc
