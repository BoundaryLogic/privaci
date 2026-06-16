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
    attr_01 text,
    attr_02 text,
    attr_03 text,
    attr_04 text,
    attr_05 text,
    attr_06 text,
    attr_07 text,
    attr_08 text,
    attr_09 text,
    attr_10 text,
    attr_11 text,
    attr_12 text,
    attr_13 text,
    attr_14 text,
    attr_15 text,
    attr_16 text,
    attr_17 text,
    attr_18 text,
    attr_19 text,
    attr_20 text,
    attr_21 text,
    attr_22 text,
    attr_23 text,
    attr_24 text,
    attr_25 text,
    attr_26 text,
    attr_27 text,
    attr_28 text,
    attr_29 text,
    attr_30 text,
    attr_31 text,
    attr_32 text,
    attr_33 text,
    attr_34 text,
    attr_35 text,
    attr_36 text,
    attr_37 text,
    attr_38 text,
    attr_39 text,
    attr_40 text,
    attr_41 text,
    attr_42 text,
    attr_43 text,
    attr_44 text,
    attr_45 text,
    attr_46 text,
    attr_47 text,
    attr_48 text,
    attr_49 text,
    attr_50 text,
    attr_51 text,
    attr_52 text,
    attr_53 text,
    attr_54 text,
    attr_55 text,
    PRIMARY KEY (id, event_at)
) PARTITION BY RANGE (event_at);

CREATE TABLE public.geo_locations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    region_path ltree
);
