-- Role without CREATE on schema → pre-flight / DDL permission failures
CREATE SCHEMA IF NOT EXISTS edge_cases;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fixture_ro') THEN
        CREATE ROLE fixture_ro LOGIN PASSWORD 'ro' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS edge_cases.permission_probe (
    id integer PRIMARY KEY
);

REVOKE ALL ON SCHEMA edge_cases FROM fixture_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA edge_cases FROM fixture_ro;
GRANT USAGE ON SCHEMA edge_cases TO fixture_ro;
GRANT SELECT ON edge_cases.permission_probe TO fixture_ro;
