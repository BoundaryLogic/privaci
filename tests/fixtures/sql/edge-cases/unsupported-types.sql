-- Custom domain column → text-mode COPY fallback on replicate/stream
CREATE SCHEMA IF NOT EXISTS edge_cases;

CREATE DOMAIN edge_cases.geo_label AS text
    CHECK (VALUE ~ '^[A-Z]{2}:[a-z0-9._-]+$');

CREATE TABLE edge_cases.geo_samples (
    id integer PRIMARY KEY,
    region edge_cases.geo_label NOT NULL
);

INSERT INTO edge_cases.geo_samples (id, region) VALUES (1, 'US:east.1');
