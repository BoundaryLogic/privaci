-- Multi-row, multi-table DEFERRABLE FK cycle for the beta-gate e2e (§18.4).
-- Exercises topological ordering + SET CONSTRAINTS ALL DEFERRED across a
-- two-table cycle (departments <-> employees) plus a self-referential cycle
-- (employees.manager_id). Carries PII (full_name, email) so masking, row
-- parity, and referential integrity are all verified in one run.
--
-- No real PII: every value is synthetic and uses the example.test domain.

DROP SCHEMA IF EXISTS beta_cycle CASCADE;
CREATE SCHEMA beta_cycle;

CREATE TABLE beta_cycle.departments (
    id integer PRIMARY KEY,
    name text NOT NULL,
    lead_id integer
);

CREATE TABLE beta_cycle.employees (
    id integer PRIMARY KEY,
    full_name text NOT NULL,
    email text NOT NULL,
    manager_id integer,
    dept_id integer NOT NULL
);

ALTER TABLE beta_cycle.employees
    ADD CONSTRAINT employees_dept_fk
    FOREIGN KEY (dept_id) REFERENCES beta_cycle.departments (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE beta_cycle.employees
    ADD CONSTRAINT employees_manager_fk
    FOREIGN KEY (manager_id) REFERENCES beta_cycle.employees (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE beta_cycle.departments
    ADD CONSTRAINT departments_lead_fk
    FOREIGN KEY (lead_id) REFERENCES beta_cycle.employees (id)
    DEFERRABLE INITIALLY DEFERRED;

-- Constraints are INITIALLY DEFERRED, so cross-references resolve at commit.
INSERT INTO beta_cycle.departments (id, name, lead_id)
SELECT g, 'Department ' || g, NULL
FROM generate_series(1, 5) AS g;

INSERT INTO beta_cycle.employees (id, full_name, email, manager_id, dept_id)
SELECT
    g,
    'Employee Number ' || g,
    'employee' || g || '@example.test',
    CASE WHEN g <= 5 THEN NULL ELSE ((g % 5) + 1) END,
    ((g % 5) + 1)
FROM generate_series(1, 30) AS g;

-- Each department is led by the like-numbered employee (ids 1..5 exist).
UPDATE beta_cycle.departments d SET lead_id = d.id;
