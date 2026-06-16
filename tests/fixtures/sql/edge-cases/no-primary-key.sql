-- Append-only table with no primary key → table-level checkpoint fallback
CREATE SCHEMA IF NOT EXISTS edge_cases;

CREATE TABLE edge_cases.events_no_pk (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_id bigint,
    action text NOT NULL,
    payload jsonb
);

INSERT INTO edge_cases.events_no_pk (action, payload)
VALUES ('login', '{"ip": "10.0.0.1"}'::jsonb);
