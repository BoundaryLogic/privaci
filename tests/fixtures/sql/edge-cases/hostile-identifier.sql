-- Table and column names containing embedded double-quotes exercise
-- quote_pg_identifier (harden-review-findings §2.9). Naive f'"{name}"'
-- interpolation would allow SQL injection; the helper must double quotes.

DROP SCHEMA IF EXISTS beta_hostile CASCADE;
CREATE SCHEMA beta_hostile;

CREATE TABLE beta_hostile."evil""table" (
    id integer PRIMARY KEY,
    email text NOT NULL,
    "weird""col" text NOT NULL
);

INSERT INTO beta_hostile."evil""table" (id, email, "weird""col")
SELECT g, 'hostile' || g || '@example.test', 'Hostile Person ' || g
FROM generate_series(1, 20) AS g;
