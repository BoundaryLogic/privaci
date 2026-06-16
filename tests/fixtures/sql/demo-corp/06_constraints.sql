-- Deferred FKs breaking the organizations <-> users cycle
ALTER TABLE public.users
    ADD CONSTRAINT users_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id),
    ADD CONSTRAINT users_manager_fk
        FOREIGN KEY (manager_id) REFERENCES public.users (id);

ALTER TABLE public.organizations
    ADD CONSTRAINT organizations_owner_fk
        FOREIGN KEY (owner_user_id) REFERENCES public.users (id)
        DEFERRABLE INITIALLY DEFERRED,
    ADD CONSTRAINT organizations_primary_user_fk
        FOREIGN KEY (primary_user_id) REFERENCES public.users (id)
        DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE public.subscriptions
    ADD CONSTRAINT subscriptions_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id);

ALTER TABLE public.invoices
    ADD CONSTRAINT invoices_subscription_fk
        FOREIGN KEY (subscription_id) REFERENCES public.subscriptions (id);

ALTER TABLE public.invoice_line_items
    ADD CONSTRAINT invoice_line_items_invoice_fk
        FOREIGN KEY (invoice_id) REFERENCES public.invoices (id);

ALTER TABLE public.user_addresses
    ADD CONSTRAINT user_addresses_user_fk
        FOREIGN KEY (user_id) REFERENCES public.users (id);

ALTER TABLE public.user_payment_methods
    ADD CONSTRAINT user_payment_methods_user_fk
        FOREIGN KEY (user_id) REFERENCES public.users (id);

ALTER TABLE public.employees
    ADD CONSTRAINT employees_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id),
    ADD CONSTRAINT employees_manager_fk
        FOREIGN KEY (manager_id) REFERENCES public.employees (id);

ALTER TABLE public.tickets
    ADD CONSTRAINT tickets_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id),
    ADD CONSTRAINT tickets_reporter_fk
        FOREIGN KEY (reporter_user_id) REFERENCES public.users (id),
    ADD CONSTRAINT tickets_assigned_fk
        FOREIGN KEY (assigned_to_user_id) REFERENCES public.users (id);

ALTER TABLE public.ticket_messages
    ADD CONSTRAINT ticket_messages_ticket_fk
        FOREIGN KEY (ticket_id) REFERENCES public.tickets (id),
    ADD CONSTRAINT ticket_messages_author_fk
        FOREIGN KEY (author_user_id) REFERENCES public.users (id);

ALTER TABLE public.comments
    ADD CONSTRAINT comments_author_fk
        FOREIGN KEY (author_user_id) REFERENCES public.users (id);

ALTER TABLE clinical.providers
    ADD CONSTRAINT providers_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id);

ALTER TABLE clinical.patients
    ADD CONSTRAINT patients_provider_fk
        FOREIGN KEY (primary_provider_id) REFERENCES clinical.providers (id),
    ADD CONSTRAINT patients_org_fk
        FOREIGN KEY (org_id) REFERENCES public.organizations (id);

ALTER TABLE clinical.patient_visits
    ADD CONSTRAINT visits_patient_fk
        FOREIGN KEY (patient_id) REFERENCES clinical.patients (id),
    ADD CONSTRAINT visits_provider_fk
        FOREIGN KEY (provider_id) REFERENCES clinical.providers (id);

ALTER TABLE clinical.prescriptions
    ADD CONSTRAINT prescriptions_patient_fk
        FOREIGN KEY (patient_id) REFERENCES clinical.patients (id),
    ADD CONSTRAINT prescriptions_provider_fk
        FOREIGN KEY (provider_id) REFERENCES clinical.providers (id);

ALTER TABLE clinical.patient_documents
    ADD CONSTRAINT patient_documents_patient_fk
        FOREIGN KEY (patient_id) REFERENCES clinical.patients (id);

ALTER TABLE auth.sessions
    ADD CONSTRAINT sessions_user_fk
        FOREIGN KEY (user_id) REFERENCES public.users (id);

ALTER TABLE auth.api_keys
    ADD CONSTRAINT api_keys_user_fk
        FOREIGN KEY (user_id) REFERENCES public.users (id);
