-- Single wide table with enough rows to span many batches for the resume
-- e2e (§18.6). A crash is injected mid-stream; the resumed run must reach
-- exact row parity with zero duplicates.
--
-- No real PII: every value is synthetic and uses the example.test domain.

DROP SCHEMA IF EXISTS beta_resume CASCADE;
CREATE SCHEMA beta_resume;

CREATE TABLE beta_resume.records (
    id integer PRIMARY KEY,
    email text NOT NULL,
    full_name text NOT NULL
);

INSERT INTO beta_resume.records (id, email, full_name)
SELECT g, 'record' || g || '@example.test', 'Record Person ' || g
FROM generate_series(1, 100) AS g;
