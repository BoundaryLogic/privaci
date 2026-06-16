CREATE TABLE audit_internal.audit_log_events (
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint,
    action text NOT NULL,
    target text,
    payload jsonb
);
