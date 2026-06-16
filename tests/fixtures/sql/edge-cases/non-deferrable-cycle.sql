-- Two-table FK cycle with NOT DEFERRABLE constraints → catalog load-plan exit 2
CREATE SCHEMA IF NOT EXISTS edge_cases;

CREATE TABLE edge_cases.cycle_a (
    id integer PRIMARY KEY,
    b_id integer
);

CREATE TABLE edge_cases.cycle_b (
    id integer PRIMARY KEY,
    a_id integer
);

ALTER TABLE edge_cases.cycle_a
    ADD CONSTRAINT cycle_a_b_id_fkey
    FOREIGN KEY (b_id) REFERENCES edge_cases.cycle_b (id)
    NOT DEFERRABLE;

ALTER TABLE edge_cases.cycle_b
    ADD CONSTRAINT cycle_b_a_id_fkey
    FOREIGN KEY (a_id) REFERENCES edge_cases.cycle_a (id)
    NOT DEFERRABLE;
