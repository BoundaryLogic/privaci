"""``audit_internal`` schema DDL for Demo Corp."""

from __future__ import annotations


def audit_ddl() -> str:
    """Return ``CREATE TABLE`` for ``audit_internal`` (no primary key)."""
    return """\
CREATE TABLE audit_internal.audit_log_events (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint,
    action text NOT NULL,
    target text,
    payload jsonb
);
"""
