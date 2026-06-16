"""``public`` schema DDL for Demo Corp."""

from __future__ import annotations


def public_ddl() -> str:
    """Return ``CREATE TABLE`` statements for the ``public`` schema."""
    wide_cols = ",\n    ".join(f"attr_{idx:02d} text" for idx in range(1, 56))
    return f"""\
-- public schema tables
CREATE TABLE public.organizations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    ein text,
    billing_email text UNIQUE,
    owner_user_id bigint,
    primary_user_id bigint
);

CREATE TABLE public.users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    phone text,
    first_name text,
    last_name text,
    dob date,
    ssn text,
    password_hash text,
    role text NOT NULL DEFAULT 'user',
    org_id bigint NOT NULL,
    manager_id bigint,
    last_login_ip inet
);

CREATE TABLE public.subscriptions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id bigint NOT NULL,
    plan text NOT NULL,
    started_at date NOT NULL,
    billing_address_id bigint
);

CREATE TABLE public.invoices (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subscription_id bigint NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    total_cents bigint NOT NULL
);

CREATE TABLE public.invoice_line_items (
    invoice_id bigint NOT NULL,
    line_no int NOT NULL,
    description text,
    amount_cents bigint NOT NULL,
    PRIMARY KEY (invoice_id, line_no)
);

CREATE TABLE public.user_addresses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL,
    street text,
    city text,
    state text,
    postcode text,
    country text DEFAULT 'US'
);

CREATE TABLE public.user_payment_methods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL,
    card_number text,
    cvv text,
    expiry_month int,
    expiry_year int,
    cardholder_name text
);

CREATE TABLE public.employees (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id bigint NOT NULL,
    manager_id bigint,
    full_name text NOT NULL,
    ssn text,
    dob date,
    hire_date date,
    salary numeric(12, 2),
    npi text
);

CREATE TABLE public.tickets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id bigint NOT NULL,
    reporter_user_id bigint NOT NULL,
    assigned_to_user_id bigint,
    subject text NOT NULL,
    status text NOT NULL DEFAULT 'open',
    priority text NOT NULL DEFAULT 'normal'
);

CREATE TABLE public.ticket_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id bigint NOT NULL,
    author_user_id bigint NOT NULL,
    body text,
    posted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.comments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    commentable_type text NOT NULL,
    commentable_id bigint NOT NULL,
    author_user_id bigint NOT NULL,
    body text
);

CREATE TABLE public.raw_events (
    id bigint GENERATED ALWAYS AS IDENTITY,
    event_at timestamptz NOT NULL,
    org_id bigint NOT NULL,
    user_id bigint,
    event_type text NOT NULL,
    payload jsonb,
    {wide_cols},
    PRIMARY KEY (id, event_at)
) PARTITION BY RANGE (event_at);

CREATE TABLE public.geo_locations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    region_path ltree
);
"""
