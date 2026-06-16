CREATE TABLE clinical.providers (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    npi text NOT NULL UNIQUE,
    dea_number text,
    first_name text,
    last_name text,
    email text UNIQUE,
    specialty text,
    org_id bigint NOT NULL
);

CREATE TABLE clinical.patients (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mrn text NOT NULL UNIQUE,
    first_name text,
    last_name text,
    full_name text,
    dob date,
    ssn text,
    phone text,
    email text,
    primary_provider_id bigint,
    org_id bigint NOT NULL,
    insurance_member_id text,
    insurance_group text
);

CREATE TABLE clinical.patient_visits (
    id bigint GENERATED ALWAYS AS IDENTITY,
    patient_id bigint NOT NULL,
    provider_id bigint NOT NULL,
    visit_date date NOT NULL,
    visit_type text,
    region_code text NOT NULL,
    diagnosis_code text,
    chief_complaint text,
    visit_notes text,
    PRIMARY KEY (id, region_code)
) PARTITION BY LIST (region_code);

CREATE TABLE clinical.prescriptions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id bigint NOT NULL,
    provider_id bigint NOT NULL,
    drug_name text NOT NULL,
    dosage text,
    refills int,
    prescribed_at date
);

CREATE TABLE clinical.patient_documents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id bigint NOT NULL,
    referring_provider_email text,
    document_blob bytea,
    uploaded_by_user_email text
);
