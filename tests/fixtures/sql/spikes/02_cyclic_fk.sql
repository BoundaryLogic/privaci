-- Cyclic FK tables for SET CONSTRAINTS ALL DEFERRED spike (§2.3).

CREATE TABLE IF NOT EXISTS spike_cycle_a (
    id integer PRIMARY KEY,
    b_id integer
);

CREATE TABLE IF NOT EXISTS spike_cycle_b (
    id integer PRIMARY KEY,
    a_id integer
);

ALTER TABLE spike_cycle_a DROP CONSTRAINT IF EXISTS spike_cycle_a_b_id_fkey;
ALTER TABLE spike_cycle_b DROP CONSTRAINT IF EXISTS spike_cycle_b_a_id_fkey;

ALTER TABLE spike_cycle_a
    ADD CONSTRAINT spike_cycle_a_b_id_fkey
    FOREIGN KEY (b_id) REFERENCES spike_cycle_b (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE spike_cycle_b
    ADD CONSTRAINT spike_cycle_b_a_id_fkey
    FOREIGN KEY (a_id) REFERENCES spike_cycle_a (id)
    DEFERRABLE INITIALLY DEFERRED;

TRUNCATE spike_cycle_a, spike_cycle_b CASCADE;
