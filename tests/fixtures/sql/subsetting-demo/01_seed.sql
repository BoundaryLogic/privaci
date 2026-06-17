-- Three tenants: org 1 (2 users, 4 orders), org 2 (3 users, 9 orders), org 3 (5 users, 10 orders).
-- Full corpus: 3 orgs, 10 users, 23 orders. Subset root id=1 → 1 org, 2 users, 4 orders (~19% rows).

INSERT INTO public.organizations (id, name) VALUES
    (1, 'Acme North'),
    (2, 'Beta Labs'),
    (3, 'Gamma Works');

INSERT INTO public.users (id, org_id, email) VALUES
    (101, 1, 'alice@acme-north.example'),
    (102, 1, 'bob@acme-north.example'),
    (201, 2, 'carol@beta.example'),
    (202, 2, 'dave@beta.example'),
    (203, 2, 'erin@beta.example'),
    (301, 3, 'frank@gamma.example'),
    (302, 3, 'gina@gamma.example'),
    (303, 3, 'henry@gamma.example'),
    (304, 3, 'iris@gamma.example'),
    (305, 3, 'jake@gamma.example');

INSERT INTO public.orders (id, user_id, amount_cents) VALUES
    (1001, 101, 1200),
    (1002, 101, 3400),
    (1003, 102, 800),
    (1004, 102, 1500),
    (2001, 201, 500),
    (2002, 201, 600),
    (2003, 201, 700),
    (2004, 202, 900),
    (2005, 202, 1000),
    (2006, 202, 1100),
    (2007, 203, 1300),
    (2008, 203, 1400),
    (2009, 203, 1500),
    (3001, 301, 200),
    (3002, 301, 250),
    (3003, 302, 300),
    (3004, 302, 350),
    (3005, 303, 400),
    (3006, 303, 450),
    (3007, 304, 500),
    (3008, 304, 550),
    (3009, 305, 600),
    (3010, 305, 650);
