"""Tier-1 programmatic mini-schemas for per-test Postgres fixtures.

Each builder returns a :class:`MiniSchema` with DDL and optional seed DML.
Tests apply the SQL against an isolated schema and drop it in teardown.
"""

# ruff: noqa: S608 — SQL is assembled from fixed fixture helpers, not user input.

from __future__ import annotations

from dataclasses import dataclass

from tests.fixtures.constants import DEMO_CORP_STATIC_PASSWORD
from tests.fixtures.demo_corp.seed import fixture_email, fixture_phone, fixture_ssn


@dataclass(frozen=True, slots=True)
class MiniSchema:
    """DDL and optional DML for a minimal schema subset."""

    schema_name: str
    ddl: str
    dml: str = ""

    @property
    def sql(self) -> str:
        """Return combined DDL and DML in apply order."""
        if self.dml:
            return f"{self.ddl}\n{self.dml}"
        return self.ddl


def orgs_users_cycle(*, schema: str = "mini_demo") -> MiniSchema:
    """Deferred org↔user cycle with representative PII columns."""
    ddl = f"""\
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE {schema}.organizations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    billing_email text UNIQUE,
    owner_user_id bigint,
    primary_user_id bigint
);

CREATE TABLE {schema}.users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    phone text,
    first_name text NOT NULL,
    last_name text NOT NULL,
    ssn text,
    password_hash text NOT NULL,
    org_id bigint NOT NULL,
    manager_id bigint
);

ALTER TABLE {schema}.users
    ADD CONSTRAINT users_org_id_fkey
    FOREIGN KEY (org_id) REFERENCES {schema}.organizations (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE {schema}.organizations
    ADD CONSTRAINT orgs_owner_user_id_fkey
    FOREIGN KEY (owner_user_id) REFERENCES {schema}.users (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE {schema}.organizations
    ADD CONSTRAINT orgs_primary_user_id_fkey
    FOREIGN KEY (primary_user_id) REFERENCES {schema}.users (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE {schema}.users
    ADD CONSTRAINT users_manager_id_fkey
    FOREIGN KEY (manager_id) REFERENCES {schema}.users (id)
    DEFERRABLE INITIALLY DEFERRED;
"""
    dml = f"""
INSERT INTO {schema}.organizations (name, billing_email)
VALUES ('Acme Clinic', '{fixture_email("billing", 1)}');

INSERT INTO {schema}.users (
    email, phone, first_name, last_name, ssn, password_hash, org_id
) VALUES
    ('{fixture_email("user", 1)}', '{fixture_phone(1)}', 'Pat', 'One',
     '{fixture_ssn(1)}', 'hash-1', 1),
    ('{fixture_email("user", 2)}', '{fixture_phone(2)}', 'Pat', 'Two',
     '{fixture_ssn(2)}', 'hash-2', 1);

UPDATE {schema}.organizations
SET owner_user_id = 1, primary_user_id = 2
WHERE id = 1;

UPDATE {schema}.users SET manager_id = 1 WHERE id = 2;
"""
    return MiniSchema(schema_name=schema, ddl=ddl, dml=dml)


def users_only(*, schema: str = "mini_demo", rows: int = 3) -> MiniSchema:
    """Single-table users slice for fast masking tests."""
    ddl = f"""\
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE {schema}.users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    phone text,
    password_hash text NOT NULL
);
"""
    values = ",\n    ".join(
        f"('{fixture_email('user', idx)}', '{fixture_phone(idx)}', "
        f"'{DEMO_CORP_STATIC_PASSWORD}')"
        for idx in range(1, rows + 1)
    )
    dml = (
        f"INSERT INTO {schema}.users (email, phone, password_hash) "
        f"VALUES\n    {values};\n"
    )
    return MiniSchema(schema_name=schema, ddl=ddl, dml=dml)


def composite_pk_line_items(*, schema: str = "mini_demo") -> MiniSchema:
    """Invoice line items with composite primary key only."""
    ddl = f"""\
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE {schema}.invoices (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    total_cents bigint NOT NULL
);

CREATE TABLE {schema}.invoice_line_items (
    invoice_id bigint NOT NULL REFERENCES {schema}.invoices (id),
    line_no int NOT NULL,
    description text,
    amount_cents bigint NOT NULL,
    PRIMARY KEY (invoice_id, line_no)
);
"""
    dml = f"""
INSERT INTO {schema}.invoices (total_cents) VALUES (1000);
INSERT INTO {schema}.invoice_line_items (invoice_id, line_no, description, amount_cents)
VALUES (1, 1, 'Line one', 600), (1, 2, 'Line two', 400);
"""
    return MiniSchema(schema_name=schema, ddl=ddl, dml=dml)


def audit_events_no_pk(*, schema: str = "mini_demo") -> MiniSchema:
    """Append-only audit table without a primary key."""
    ddl = f"""\
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE {schema}.audit_log_events (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint,
    action text NOT NULL,
    payload jsonb
);
"""
    dml = f"""
INSERT INTO {schema}.audit_log_events (action, payload)
VALUES ('login', '{{"ip": "10.0.0.1"}}'::jsonb);
"""
    return MiniSchema(schema_name=schema, ddl=ddl, dml=dml)
