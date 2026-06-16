-- ~550 synthetic rows for the evaluation compose stack.

TRUNCATE public.users, public.organizations RESTART IDENTITY CASCADE;

INSERT INTO public.organizations (name)
SELECT 'Evaluation Org ' || gs
FROM generate_series(1, 50) AS gs;

INSERT INTO public.users (org_id, email, first_name, last_name, phone)
SELECT
    ((gs - 1) % 50) + 1,
    'user' || gs || '@example.test',
    'First' || gs,
    'Last' || gs,
    '+1555' || lpad(gs::text, 7, '0')
FROM generate_series(1, 500) AS gs;

ANALYZE public.organizations;
ANALYZE public.users;
