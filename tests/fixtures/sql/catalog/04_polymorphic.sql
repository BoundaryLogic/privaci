-- Rails-style polymorphic association without catalog FK

CREATE TABLE catalog_demo.comments (
    id bigint PRIMARY KEY,
    commentable_type text NOT NULL,
    commentable_id bigint NOT NULL,
    body text NOT NULL
);

ANALYZE catalog_demo.comments;
