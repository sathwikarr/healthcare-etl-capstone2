-- =====================================================
-- Healthcare ETL — Star Schema DDL
-- Target: PostgreSQL (healthcare_etl database)
-- =====================================================

-- Drop in dependency order (fact first, then dims) for clean re-runs
DROP TABLE IF EXISTS fact_treatment;
DROP TABLE IF EXISTS dim_appointment;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_doctor;
DROP TABLE IF EXISTS etl_audit_log;

-- =====================================================
-- Dimension: Patient
-- =====================================================
CREATE TABLE dim_patient (
    patient_id    INTEGER PRIMARY KEY,
    patient_name  VARCHAR(255),
    dob           DATE,
    gender        VARCHAR(10),
    loaded_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =====================================================
-- Dimension: Doctor
-- (Source data only has doctor_id; no doctor names exist upstream,
--  so this dimension is populated from distinct IDs at load time.)
-- =====================================================
CREATE TABLE dim_doctor (
    doctor_id  INTEGER PRIMARY KEY,
    loaded_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =====================================================
-- Dimension: Appointment
-- =====================================================
CREATE TABLE dim_appointment (
    appointment_id     INTEGER PRIMARY KEY,
    patient_id         INTEGER NOT NULL REFERENCES dim_patient(patient_id),
    doctor_id          INTEGER NOT NULL REFERENCES dim_doctor(doctor_id),
    start_time         TIMESTAMP,
    end_time           TIMESTAMP,
    duration_minutes   NUMERIC(10,2),
    overlaps_previous  BOOLEAN DEFAULT FALSE,
    loaded_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dim_appointment_patient_id ON dim_appointment(patient_id);
CREATE INDEX idx_dim_appointment_doctor_id ON dim_appointment(doctor_id);
CREATE INDEX idx_dim_appointment_start_time ON dim_appointment(start_time);

-- =====================================================
-- Fact: Treatment
-- =====================================================
CREATE TABLE fact_treatment (
    treatment_id      INTEGER PRIMARY KEY,
    appointment_id    INTEGER NOT NULL REFERENCES dim_appointment(appointment_id),
    treatment_type    VARCHAR(50),
    duration_minutes  NUMERIC(10,2),
    cost              NUMERIC(12,2),
    is_cost_outlier   BOOLEAN DEFAULT FALSE,
    cost_zscore       NUMERIC(10,4),
    loaded_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fact_treatment_appointment_id ON fact_treatment(appointment_id);
CREATE INDEX idx_fact_treatment_type ON fact_treatment(treatment_type);
CREATE INDEX idx_fact_treatment_cost ON fact_treatment(cost);

-- =====================================================
-- Audit log (populated by HealthcareETL metrics — Step 10)
-- =====================================================
CREATE TABLE etl_audit_log (
    audit_id          SERIAL PRIMARY KEY,
    run_started_at    TIMESTAMP NOT NULL,
    run_finished_at   TIMESTAMP NOT NULL,
    table_name        VARCHAR(50) NOT NULL,
    rows_in           INTEGER,
    rows_out          INTEGER,
    invalid_records   INTEGER,
    check_name        VARCHAR(100),
    logged_at         TIMESTAMP NOT NULL DEFAULT NOW()
);