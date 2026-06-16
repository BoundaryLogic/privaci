CREATE VIEW public.active_clinics_v AS
    SELECT id, name FROM public.organizations WHERE billing_email IS NOT NULL;

CREATE VIEW public.monthly_revenue_v AS
    SELECT date_trunc('month', period_start) AS month, sum(total_cents) AS revenue
    FROM public.invoices
    GROUP BY 1;

CREATE MATERIALIZED VIEW public.tickets_open_mv AS
    SELECT id, subject, status FROM public.tickets WHERE status <> 'closed';
