-- Acyclic FK chain: orgs -> users -> orders -> order_items

CREATE SCHEMA IF NOT EXISTS catalog_demo;

CREATE TABLE catalog_demo.orgs (
    id integer PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE catalog_demo.users (
    id integer PRIMARY KEY,
    org_id integer NOT NULL REFERENCES catalog_demo.orgs (id),
    email text NOT NULL UNIQUE
);

CREATE TABLE catalog_demo.orders (
    id integer PRIMARY KEY,
    user_id integer NOT NULL REFERENCES catalog_demo.users (id)
);

CREATE TABLE catalog_demo.order_items (
    id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES catalog_demo.orders (id)
);

ANALYZE catalog_demo.orgs;
ANALYZE catalog_demo.users;
ANALYZE catalog_demo.orders;
ANALYZE catalog_demo.order_items;
