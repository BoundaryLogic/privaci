-- Minimal acyclic tenant graph for subsetting integration tests.
-- Root predicate ``organizations id = 1`` must pull one tenant only (no cross-org FK cycles).

DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

CREATE TABLE public.organizations (
    id bigint PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE public.users (
    id bigint PRIMARY KEY,
    org_id bigint NOT NULL REFERENCES public.organizations (id),
    email text NOT NULL
);

CREATE TABLE public.orders (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users (id),
    amount_cents integer NOT NULL
);

ANALYZE public.organizations;
ANALYZE public.users;
ANALYZE public.orders;
