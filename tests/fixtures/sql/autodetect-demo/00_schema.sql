-- Minimal schema for Postgres auto-detect integration tests.

DROP SCHEMA IF EXISTS autodetect_demo CASCADE;
CREATE SCHEMA autodetect_demo;

CREATE TABLE autodetect_demo.contacts (
    id bigint PRIMARY KEY,
    email text NOT NULL,
    notes text,
    status text NOT NULL
);

INSERT INTO autodetect_demo.contacts (id, email, notes, status) VALUES
    (1, 'alice@example.test', 'Call back about billing', 'active'),
    (2, 'bob@example.test', 'No PII here', 'inactive');

ANALYZE autodetect_demo.contacts;
