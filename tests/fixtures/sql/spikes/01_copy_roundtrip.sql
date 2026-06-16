-- Schema for COPY-binary round-trip spike (§2.1).
-- Loaded automatically when source-pg starts via compose.dev.yml.

CREATE TABLE IF NOT EXISTS spike_copy_roundtrip (
    id integer PRIMARY KEY,
    label text NOT NULL,
    amount numeric(12, 2),
    active boolean NOT NULL DEFAULT true,
    payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

TRUNCATE spike_copy_roundtrip;

INSERT INTO spike_copy_roundtrip (id, label, amount, active, payload)
VALUES
    (1, 'alpha', 10.50, true, '{"tier": "a"}'::jsonb),
    (2, 'beta', 0.00, false, '{"tier": "b"}'::jsonb),
    (3, 'gamma', 999999.99, true, null);
