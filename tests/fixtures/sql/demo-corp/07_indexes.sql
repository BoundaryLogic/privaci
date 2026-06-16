CREATE UNIQUE INDEX patients_name_dob_uq
    ON clinical.patients (first_name, last_name, dob);
