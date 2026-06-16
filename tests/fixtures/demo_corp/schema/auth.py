"""``auth`` schema DDL for Demo Corp."""

from __future__ import annotations


def auth_ddl() -> str:
    """Return ``CREATE TABLE`` statements for the ``auth`` schema."""
    return """\
CREATE TABLE auth.sessions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL,
    token uuid NOT NULL UNIQUE,
    ip_address inet,
    user_agent text,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);

CREATE TABLE auth.api_keys (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL,
    key_hash text NOT NULL,
    last_used_at timestamptz,
    last_used_ip inet,
    scopes text[]
);
"""
