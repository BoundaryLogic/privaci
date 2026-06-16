-- Polymorphic ("soft") FK schema for the beta-gate e2e (§18.5).
-- `comments.commentable_type` / `commentable_id` form a Rails-style polymorphic
-- association with no catalog foreign key. The engine cannot enforce its
-- integrity, so it must emit a polymorphic_fk_warning and still complete the run.
--
-- No real PII: every value is synthetic and uses the example.test domain.

DROP SCHEMA IF EXISTS beta_poly CASCADE;
CREATE SCHEMA beta_poly;

CREATE TABLE beta_poly.users (
    id integer PRIMARY KEY,
    email text NOT NULL
);

CREATE TABLE beta_poly.posts (
    id integer PRIMARY KEY,
    title text NOT NULL
);

CREATE TABLE beta_poly.comments (
    id integer PRIMARY KEY,
    body text NOT NULL,
    author_email text NOT NULL,
    commentable_type text NOT NULL,
    commentable_id integer NOT NULL
);

INSERT INTO beta_poly.users (id, email)
SELECT g, 'user' || g || '@example.test'
FROM generate_series(1, 10) AS g;

INSERT INTO beta_poly.posts (id, title)
SELECT g, 'Post ' || g
FROM generate_series(1, 10) AS g;

INSERT INTO beta_poly.comments (id, body, author_email, commentable_type, commentable_id)
SELECT
    g,
    'Comment body ' || g,
    'author' || g || '@example.test',
    CASE WHEN g % 2 = 0 THEN 'User' ELSE 'Post' END,
    ((g % 10) + 1)
FROM generate_series(1, 20) AS g;
