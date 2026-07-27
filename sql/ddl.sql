-- =====================================================
-- Healthcare ETL — Star Schema DDL
-- Target: PostgreSQL (healthcare_etl database)
-- =====================================================

-- Drop in dependency order (fact first, then dims) for clean re-runs
DROP TABLE IF EXISTS fact_treatment CASCADE;
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
-- Fact: Treatment — PARTITIONED BY MONTH
--
-- treatment_month is a denormalized copy of the parent appointment's
-- start_time (truncated to the 1st of the month), added purely to
-- serve as the partition key — treatments have no date of their own.
-- Postgres requires the partition key to be part of the primary key
-- on a partitioned table, so the PK here is composite:
-- (treatment_id, treatment_month) instead of just treatment_id.
--
-- Query benefit: analytics queries filtered by date range (e.g.
-- "this month's treatments") only scan the relevant partition(s)
-- instead of the whole table — this is a real win once the table
-- reaches millions of rows, even though at capstone scale (~6k rows)
-- the practical speedup is negligible. Implemented anyway as a
-- deliberate demonstration of the pattern.
-- =====================================================
CREATE TABLE fact_treatment (
    treatment_id      INTEGER NOT NULL,
    appointment_id    INTEGER NOT NULL REFERENCES dim_appointment(appointment_id),
    treatment_type    VARCHAR(50),
    duration_minutes  NUMERIC(10,2),
    cost              NUMERIC(12,2),
    is_cost_outlier   BOOLEAN DEFAULT FALSE,
    cost_zscore       NUMERIC(10,4),
    treatment_month   DATE NOT NULL,
    loaded_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (treatment_id, treatment_month)
) PARTITION BY RANGE (treatment_month);

-- Catch-all partition for any date outside the explicit monthly
-- ranges below (safety net — should stay empty in normal operation).
CREATE TABLE fact_treatment_default PARTITION OF fact_treatment DEFAULT;

-- Monthly partitions covering Jan 2024 – Dec 2026 (36 months).
-- Generated with a DO block rather than 36 hand-written CREATE TABLE
-- statements — same effect, far less repetition.
DO $$
DECLARE
    partition_start DATE := '2024-01-01';
    partition_end   DATE;
    partition_name  TEXT;
BEGIN
    WHILE partition_start < '2027-01-01' LOOP
        partition_end := partition_start + INTERVAL '1 month';
        partition_name := 'fact_treatment_' || TO_CHAR(partition_start, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE %I PARTITION OF fact_treatment
                FOR VALUES FROM (%L) TO (%L)',
            partition_name, partition_start, partition_end
        );

        partition_start := partition_end;
    END LOOP;
END $$;

-- Indexes on the partitioned (parent) table — Postgres automatically
-- creates a matching index on every existing and future partition.
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