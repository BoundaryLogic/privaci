-- Cyclic FK between orders_cycle and users_cycle

CREATE TABLE catalog_demo.users_cycle (
    id integer PRIMARY KEY,
    last_order_id integer
);

CREATE TABLE catalog_demo.orders_cycle (
    id integer PRIMARY KEY,
    user_id integer
);

ALTER TABLE catalog_demo.users_cycle
    ADD CONSTRAINT users_cycle_last_order_id_fkey
    FOREIGN KEY (last_order_id) REFERENCES catalog_demo.orders_cycle (id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE catalog_demo.orders_cycle
    ADD CONSTRAINT orders_cycle_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES catalog_demo.users_cycle (id)
    DEFERRABLE INITIALLY DEFERRED;

ANALYZE catalog_demo.users_cycle;
ANALYZE catalog_demo.orders_cycle;
