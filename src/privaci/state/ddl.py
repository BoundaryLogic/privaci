"""DDL for the ``_privaci`` state schema.

All statements are idempotent (``CREATE ... IF NOT EXISTS``) so they can run on
every engine start. Status columns use ``text`` + ``CHECK`` rather than native
enum types because ``CREATE TYPE`` is not idempotent and additive migrations on
``CHECK`` lists are simpler than ``ALTER TYPE``.

``STATE_SCHEMA_VERSION`` is bumped whenever the physical layout changes. The
engine refuses to run against a ``_privaci`` schema written by a newer version
(see :mod:`privaci.state.schema`).
"""

from __future__ import annotations

STATE_SCHEMA_NAME = "_privaci"
STATE_SCHEMA_VERSION = 1

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS _privaci"

CREATE_SCHEMA_METADATA_SQL = """
CREATE TABLE IF NOT EXISTS _privaci.schema_metadata (
    singleton boolean PRIMARY KEY DEFAULT true,
    schema_version integer NOT NULL,
    engine_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT schema_metadata_singleton CHECK (singleton)
)
"""

CREATE_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS _privaci.runs (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    status text NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'succeeded', 'failed', 'interrupted')),
    engine_version text NOT NULL,
    config_hash text NOT NULL,
    salt_fingerprint text NOT NULL,
    source_db_hash text NOT NULL,
    source_schema_snapshot jsonb,
    summary jsonb
)
"""

CREATE_TABLE_CHECKPOINTS_SQL = """
CREATE TABLE IF NOT EXISTS _privaci.table_checkpoints (
    run_id uuid NOT NULL REFERENCES _privaci.runs (run_id) ON DELETE CASCADE,
    schema_name text NOT NULL,
    table_name text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    last_pk_value text,
    rows_processed bigint NOT NULL DEFAULT 0,
    last_update_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, schema_name, table_name)
)
"""

CREATE_AUDIT_LOG_SQL = """
CREATE TABLE IF NOT EXISTS _privaci.audit_log (
    audit_id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES _privaci.runs (run_id) ON DELETE CASCADE,
    event_at timestamptz NOT NULL DEFAULT now(),
    level text NOT NULL DEFAULT 'info'
        CHECK (level IN ('info', 'warning', 'error')),
    event_type text NOT NULL,
    schema_name text,
    table_name text,
    column_name text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
)
"""

CREATE_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS audit_log_run_id_idx " "ON _privaci.audit_log (run_id)",
    "CREATE INDEX IF NOT EXISTS runs_source_db_hash_idx "
    "ON _privaci.runs (source_db_hash)",
)

# Ordered so foreign-key targets exist before referencing tables.
DDL_STATEMENTS: tuple[str, ...] = (
    CREATE_SCHEMA_SQL,
    CREATE_SCHEMA_METADATA_SQL,
    CREATE_RUNS_SQL,
    CREATE_TABLE_CHECKPOINTS_SQL,
    CREATE_AUDIT_LOG_SQL,
    *CREATE_INDEXES_SQL,
)
