-- JSONB column for commercial json_mask integration tests.

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

CREATE TABLE public.event_log (
    id bigint PRIMARY KEY,
    payload jsonb NOT NULL
);

INSERT INTO public.event_log (id, payload) VALUES
    (
        1,
        '{"contact":{"email":"alice@acme.example","name":"Alice"},"token":"secret-tok","debug":"trace","note":"hello"}'::jsonb
    ),
    (
        2,
        '{"contact":{"email":"bob@acme.example","name":"Bob"},"token":"other-tok","debug":"trace2","note":"world"}'::jsonb
    );

ANALYZE public.event_log;
