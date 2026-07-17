-- Tier 1: non-elevated SQL function (no table deps — safe under strategy:exclude)
CREATE OR REPLACE FUNCTION public.clinic_label(org_id bigint)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT 'clinic-' || org_id::text
$$;

-- Tier 1: elevated SECURITY DEFINER function (disposition required)
CREATE OR REPLACE FUNCTION public.elevated_org_name(org_id bigint)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT name FROM public.organizations WHERE id = org_id
$$;

-- Tier 1: invoker-rights views (default-on replication)
CREATE VIEW public.active_clinics_v
    WITH (security_invoker = true) AS
    SELECT id, name FROM public.organizations WHERE billing_email IS NOT NULL;

CREATE VIEW public.monthly_revenue_v
    WITH (security_invoker = true) AS
    SELECT date_trunc('month', period_start) AS month, sum(total_cents) AS revenue
    FROM public.invoices
    GROUP BY 1;

-- Tier 1: elevated view (default rights / non-invoker — disposition required)
CREATE VIEW public.elevated_orgs_v AS
    SELECT id, name, billing_email FROM public.organizations;

-- Tier 2: materialized view (definition-only; opt-in via
-- replicate_materialized_views + optional refresh_materialized_views)
CREATE MATERIALIZED VIEW public.tickets_open_mv AS
    SELECT id, subject, status FROM public.tickets WHERE status <> 'closed';

-- Tier 3: trigger function + trigger (skipped_object / unsafe_during_load)
CREATE OR REPLACE FUNCTION public.users_audit_noop()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_audit_noop
    AFTER INSERT ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.users_audit_noop();

-- Tier 3: rule (skipped_object / customer_owned_semantics)
CREATE RULE tickets_insert_also_noop AS
    ON INSERT TO public.tickets DO ALSO NOTHING;

-- Tier 3: publication (skipped_object / low_value_footgun)
CREATE PUBLICATION privaci_demo_fixture_pub FOR TABLE public.organizations;
