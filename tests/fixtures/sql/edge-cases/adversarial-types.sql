-- Adversarial value/shape coverage for the streaming + masking path:
--   * a deep 4-level foreign-key chain (tier1 -> tier2 -> tier3 -> tier4),
--   * 4-byte UTF-8 (emoji, mathematical alphanumerics) and combining glyphs,
--   * large jsonb payloads, max-width numeric, arrays with quotes/commas,
--     bytea, inet, and timestamptz.
--
-- A non-PII column must round-trip byte-for-byte through COPY; a PII column
-- (email) must be masked. No real PII: every value is synthetic.

DROP SCHEMA IF EXISTS beta_adversarial CASCADE;
CREATE SCHEMA beta_adversarial;

CREATE TABLE beta_adversarial.tier1 (
    id integer PRIMARY KEY,
    label text NOT NULL
);
CREATE TABLE beta_adversarial.tier2 (
    id integer PRIMARY KEY,
    tier1_id integer NOT NULL REFERENCES beta_adversarial.tier1 (id),
    label text NOT NULL
);
CREATE TABLE beta_adversarial.tier3 (
    id integer PRIMARY KEY,
    tier2_id integer NOT NULL REFERENCES beta_adversarial.tier2 (id),
    label text NOT NULL
);
CREATE TABLE beta_adversarial.tier4 (
    id integer PRIMARY KEY,
    tier3_id integer NOT NULL REFERENCES beta_adversarial.tier3 (id),
    label text NOT NULL
);

CREATE TABLE beta_adversarial.exotic (
    id integer PRIMARY KEY,
    email text NOT NULL,
    notes text NOT NULL,
    payload jsonb NOT NULL,
    big_num numeric(38, 0) NOT NULL,
    money_val numeric(20, 4) NOT NULL,
    tags text[] NOT NULL,
    raw bytea NOT NULL,
    created_at timestamptz NOT NULL,
    ip inet NOT NULL
);

INSERT INTO beta_adversarial.tier1 (id, label)
SELECT g, 'tier1-' || g FROM generate_series(1, 5) AS g;
INSERT INTO beta_adversarial.tier2 (id, tier1_id, label)
SELECT g, ((g - 1) % 5) + 1, 'tier2-' || g FROM generate_series(1, 5) AS g;
INSERT INTO beta_adversarial.tier3 (id, tier2_id, label)
SELECT g, ((g - 1) % 5) + 1, 'tier3-' || g FROM generate_series(1, 5) AS g;
INSERT INTO beta_adversarial.tier4 (id, tier3_id, label)
SELECT g, ((g - 1) % 5) + 1, 'tier4-' || g FROM generate_series(1, 5) AS g;

-- 4-byte emoji (😀🚀), a 4-byte mathematical glyph (𝕏), CJK, and accented Latin.
INSERT INTO beta_adversarial.exotic
(id, email, notes, payload, big_num, money_val, tags, raw, created_at, ip)
SELECT
    g,
    'exotic' || g || '@example.test',
    '😀🚀𝕏 café — naïve — 北京 — row ' || g,
    (
        SELECT jsonb_agg(jsonb_build_object('k', s, 'v', repeat('x', 200)))
        FROM generate_series(1, 100) AS s
    ),
    99999999999999999999999999999999999999,
    1234567890123456.7890,
    ARRAY['tag' || g, '😀', 'quote"inside', 'comma,inside'],
    decode('DEADBEEF00FF', 'hex'),
    TIMESTAMPTZ '2024-01-01 00:00:00+00' + make_interval(hours => g),
    ('192.0.2.' || ((g % 254) + 1))::inet
FROM generate_series(1, 25) AS g;
