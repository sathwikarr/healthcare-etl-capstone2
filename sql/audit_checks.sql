-- =====================================================
-- Healthcare ETL — Audit Checks
-- Target: PostgreSQL (healthcare_etl database)
--
-- Purpose: independently verify, directly in SQL, that the data
-- loaded by src/etl.py is actually clean. These checks are
-- deliberately separate from the Python-side validation.py logic —
-- if the ETL has a bug, these queries should catch it even if the
-- Python code itself would have (wrongly) reported success.
-- Every query below should return 0 rows / 0 count if the load
-- is correct.
-- =====================================================


-- =====================================================
-- Check 1: No orphan treatments (appointment_id not in dim_appointment)
-- =====================================================
SELECT
    COUNT(*) AS orphan_treatment_count
FROM fact_treatment t
LEFT JOIN dim_appointment a ON a.appointment_id = t.appointment_id
WHERE a.appointment_id IS NULL;


-- =====================================================
-- Check 2: No orphan appointments (patient_id not in dim_patient)
-- =====================================================
SELECT
    COUNT(*) AS orphan_appointment_count
FROM dim_appointment a
LEFT JOIN dim_patient p ON p.patient_id = a.patient_id
WHERE p.patient_id IS NULL;


-- =====================================================
-- Check 3: No orphan appointments referencing a missing doctor
-- =====================================================
SELECT
    COUNT(*) AS orphan_doctor_count
FROM dim_appointment a
LEFT JOIN dim_doctor d ON d.doctor_id = a.doctor_id
WHERE d.doctor_id IS NULL;


-- =====================================================
-- Check 4: No duplicate appointment_id in dim_appointment
-- (Primary key already enforces this at the DB level, but this
--  check confirms it explicitly and would catch a schema regression.)
-- =====================================================
SELECT
    appointment_id,
    COUNT(*) AS occurrence_count
FROM dim_appointment
GROUP BY appointment_id
HAVING COUNT(*) > 1;


-- =====================================================
-- Check 5: No duplicate treatment_id in fact_treatment
-- =====================================================
SELECT
    treatment_id,
    COUNT(*) AS occurrence_count
FROM fact_treatment
GROUP BY treatment_id
HAVING COUNT(*) > 1;


-- =====================================================
-- Check 6: No duplicate patient_id in dim_patient
-- =====================================================
SELECT
    patient_id,
    COUNT(*) AS occurrence_count
FROM dim_patient
GROUP BY patient_id
HAVING COUNT(*) > 1;


-- =====================================================
-- Check 7: All appointment durations are non-negative
-- (A negative duration would mean end_time < start_time —
--  a logic error that should never survive the transform step.)
-- =====================================================
SELECT
    COUNT(*) AS negative_duration_count
FROM dim_appointment
WHERE duration_minutes IS NOT NULL
  AND duration_minutes < 0;


-- =====================================================
-- Check 8: All treatment durations are non-negative
-- =====================================================
SELECT
    COUNT(*) AS negative_treatment_duration_count
FROM fact_treatment
WHERE duration_minutes IS NOT NULL
  AND duration_minutes < 0;


-- =====================================================
-- Check 9: All costs are non-negative
-- =====================================================
SELECT
    COUNT(*) AS negative_cost_count
FROM fact_treatment
WHERE cost IS NOT NULL
  AND cost < 0;


-- =====================================================
-- Check 10: Row-count reconciliation against etl_audit_log
-- Confirms the most recent ETL run's logged rows_out matches
-- what's actually sitting in the warehouse right now.
-- =====================================================
SELECT
    'patients' AS table_name,
    (SELECT COUNT(*) FROM dim_patient) AS actual_row_count,
    (SELECT rows_out FROM etl_audit_log
        WHERE table_name = 'patients'
        ORDER BY logged_at DESC LIMIT 1) AS last_logged_rows_out
UNION ALL
SELECT
    'appointments',
    (SELECT COUNT(*) FROM dim_appointment),
    (SELECT rows_out FROM etl_audit_log
        WHERE table_name = 'appointments'
        ORDER BY logged_at DESC LIMIT 1)
UNION ALL
SELECT
    'treatments',
    (SELECT COUNT(*) FROM fact_treatment),
    (SELECT rows_out FROM etl_audit_log
        WHERE table_name = 'treatments'
        ORDER BY logged_at DESC LIMIT 1);


-- =====================================================
-- Summary: run all checks and flag pass/fail in one result set
-- =====================================================
SELECT 'orphan_treatments' AS check_name,
       (SELECT COUNT(*) FROM fact_treatment t
            LEFT JOIN dim_appointment a ON a.appointment_id = t.appointment_id
            WHERE a.appointment_id IS NULL) AS failing_row_count
UNION ALL
SELECT 'orphan_appointments_patient',
       (SELECT COUNT(*) FROM dim_appointment a
            LEFT JOIN dim_patient p ON p.patient_id = a.patient_id
            WHERE p.patient_id IS NULL)
UNION ALL
SELECT 'orphan_appointments_doctor',
       (SELECT COUNT(*) FROM dim_appointment a
            LEFT JOIN dim_doctor d ON d.doctor_id = a.doctor_id
            WHERE d.doctor_id IS NULL)
UNION ALL
SELECT 'duplicate_appointment_ids',
       (SELECT COUNT(*) FROM (
            SELECT appointment_id FROM dim_appointment
            GROUP BY appointment_id HAVING COUNT(*) > 1
       ) sub)
UNION ALL
SELECT 'duplicate_treatment_ids',
       (SELECT COUNT(*) FROM (
            SELECT treatment_id FROM fact_treatment
            GROUP BY treatment_id HAVING COUNT(*) > 1
       ) sub)
UNION ALL
SELECT 'duplicate_patient_ids',
       (SELECT COUNT(*) FROM (
            SELECT patient_id FROM dim_patient
            GROUP BY patient_id HAVING COUNT(*) > 1
       ) sub)
UNION ALL
SELECT 'negative_appointment_durations',
       (SELECT COUNT(*) FROM dim_appointment WHERE duration_minutes < 0)
UNION ALL
SELECT 'negative_treatment_durations',
       (SELECT COUNT(*) FROM fact_treatment WHERE duration_minutes < 0)
UNION ALL
SELECT 'negative_costs',
       (SELECT COUNT(*) FROM fact_treatment WHERE cost < 0)
ORDER BY failing_row_count DESC;