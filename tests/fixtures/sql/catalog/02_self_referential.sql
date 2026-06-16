-- Self-referential FK on employees.manager_id

CREATE TABLE catalog_demo.employees (
    id integer PRIMARY KEY,
    manager_id integer REFERENCES catalog_demo.employees (id)
        DEFERRABLE INITIALLY DEFERRED
);

ANALYZE catalog_demo.employees;
