-- Excluded parent referenced by NOT NULL child FK → config validation exit 3
CREATE SCHEMA IF NOT EXISTS edge_cases;

CREATE TABLE edge_cases.exclude_parent (
    id integer PRIMARY KEY,
    label text NOT NULL
);

CREATE TABLE edge_cases.depends_on_parent (
    id integer PRIMARY KEY,
    parent_id integer NOT NULL REFERENCES edge_cases.exclude_parent (id),
    note text
);

INSERT INTO edge_cases.exclude_parent (id, label) VALUES (1, 'parent');
INSERT INTO edge_cases.depends_on_parent (id, parent_id, note)
VALUES (1, 1, 'child');
