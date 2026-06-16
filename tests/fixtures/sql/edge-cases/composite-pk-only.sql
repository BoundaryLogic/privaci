-- Composite primary key with no single-column surrogate → keyset pagination edge
CREATE SCHEMA IF NOT EXISTS edge_cases;

CREATE TABLE edge_cases.composite_only (
    bucket_id integer NOT NULL,
    item_no integer NOT NULL,
    payload text NOT NULL,
    PRIMARY KEY (bucket_id, item_no)
);

INSERT INTO edge_cases.composite_only (bucket_id, item_no, payload)
VALUES (1, 1, 'alpha'), (1, 2, 'beta');
