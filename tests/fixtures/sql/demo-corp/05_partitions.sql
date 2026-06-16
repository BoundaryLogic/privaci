-- Range partitions for public.raw_events
CREATE TABLE public.raw_events_2024_01 PARTITION OF public.raw_events FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE public.raw_events_2024_02 PARTITION OF public.raw_events FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE public.raw_events_2024_03 PARTITION OF public.raw_events FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE public.raw_events_2024_04 PARTITION OF public.raw_events FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE public.raw_events_2024_05 PARTITION OF public.raw_events FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE public.raw_events_2024_06 PARTITION OF public.raw_events FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
CREATE TABLE public.raw_events_2024_07 PARTITION OF public.raw_events FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE public.raw_events_2024_08 PARTITION OF public.raw_events FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE public.raw_events_2024_09 PARTITION OF public.raw_events FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE public.raw_events_2024_10 PARTITION OF public.raw_events FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
CREATE TABLE public.raw_events_2024_11 PARTITION OF public.raw_events FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
CREATE TABLE public.raw_events_2024_12 PARTITION OF public.raw_events FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
CREATE TABLE public.raw_events_2025_01 PARTITION OF public.raw_events FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE public.raw_events_2025_02 PARTITION OF public.raw_events FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE public.raw_events_2025_03 PARTITION OF public.raw_events FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE public.raw_events_2025_04 PARTITION OF public.raw_events FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE public.raw_events_2025_05 PARTITION OF public.raw_events FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE public.raw_events_2025_06 PARTITION OF public.raw_events FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE public.raw_events_2025_07 PARTITION OF public.raw_events FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE public.raw_events_2025_08 PARTITION OF public.raw_events FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE public.raw_events_2025_09 PARTITION OF public.raw_events FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE public.raw_events_2025_10 PARTITION OF public.raw_events FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE public.raw_events_2025_11 PARTITION OF public.raw_events FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE public.raw_events_2025_12 PARTITION OF public.raw_events FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- List partitions for clinical.patient_visits
CREATE TABLE clinical.patient_visits_us_east PARTITION OF clinical.patient_visits FOR VALUES IN ('us_east');
CREATE TABLE clinical.patient_visits_us_west PARTITION OF clinical.patient_visits FOR VALUES IN ('us_west');
CREATE TABLE clinical.patient_visits_us_central PARTITION OF clinical.patient_visits FOR VALUES IN ('us_central');
CREATE TABLE clinical.patient_visits_intl PARTITION OF clinical.patient_visits FOR VALUES IN ('intl');
