-- =====================================================
-- Healthcare ETL — Analytics Queries
-- Target: PostgreSQL (healthcare_etl database)
-- Run against tables populated by src/etl.py (Step 8)
-- =====================================================


-- =====================================================
-- 1. Most common treatments
-- =====================================================
SELECT
    treatment_type,
    COUNT(*) AS treatment_count
FROM fact_treatment
GROUP BY treatment_type
ORDER BY treatment_count DESC;


-- =====================================================
-- 2. Average number of visits per patient
-- =====================================================
SELECT
    ROUND(AVG(visit_count), 2) AS avg_visits_per_patient
FROM (
    SELECT patient_id, COUNT(*) AS visit_count
    FROM dim_appointment
    GROUP BY patient_id
) AS visits_per_patient;


-- =====================================================
-- 3. Monthly appointment trends
-- =====================================================
SELECT
    DATE_TRUNC('month', start_time) AS month,
    COUNT(*) AS appointment_count
FROM dim_appointment
WHERE start_time IS NOT NULL
GROUP BY DATE_TRUNC('month', start_time)
ORDER BY month;


-- =====================================================
-- 4. Total cost per patient
-- =====================================================
SELECT
    p.patient_id,
    p.patient_name,
    ROUND(SUM(t.cost), 2) AS total_cost,
    COUNT(t.treatment_id) AS treatment_count
FROM dim_patient p
JOIN dim_appointment a ON a.patient_id = p.patient_id
JOIN fact_treatment t ON t.appointment_id = a.appointment_id
GROUP BY p.patient_id, p.patient_name
ORDER BY total_cost DESC;


-- =====================================================
-- 5. Average visit duration by treatment type
-- =====================================================
SELECT
    treatment_type,
    ROUND(AVG(duration_minutes), 2) AS avg_duration_minutes
FROM fact_treatment
WHERE duration_minutes IS NOT NULL
GROUP BY treatment_type
ORDER BY avg_duration_minutes DESC;


-- =====================================================
-- 6. Overlapping appointments (per doctor)
-- Uses the overlaps_previous flag computed during transform,
-- but recomputed here directly in SQL for verification.
-- =====================================================
SELECT
    a1.doctor_id,
    a1.appointment_id AS appointment_1,
    a2.appointment_id AS appointment_2,
    a1.start_time AS start_1,
    a1.end_time AS end_1,
    a2.start_time AS start_2,
    a2.end_time AS end_2
FROM dim_appointment a1
JOIN dim_appointment a2
    ON a1.doctor_id = a2.doctor_id
    AND a1.appointment_id < a2.appointment_id
    AND a1.start_time < a2.end_time
    AND a2.start_time < a1.end_time
WHERE a1.start_time IS NOT NULL
  AND a1.end_time IS NOT NULL
  AND a2.start_time IS NOT NULL
  AND a2.end_time IS NOT NULL
ORDER BY a1.doctor_id, a1.start_time;


-- =====================================================
-- 7. Frequent-visit patients (more than 5 visits)
-- =====================================================
SELECT
    p.patient_id,
    p.patient_name,
    COUNT(a.appointment_id) AS visit_count
FROM dim_patient p
JOIN dim_appointment a ON a.patient_id = p.patient_id
GROUP BY p.patient_id, p.patient_name
HAVING COUNT(a.appointment_id) > 5
ORDER BY visit_count DESC;


-- =====================================================
-- 8. Treatments performed per doctor
-- =====================================================
SELECT
    a.doctor_id,
    COUNT(t.treatment_id) AS treatment_count
FROM dim_appointment a
JOIN fact_treatment t ON t.appointment_id = a.appointment_id
GROUP BY a.doctor_id
ORDER BY treatment_count DESC;


-- =====================================================
-- 9. Cost outliers (top 1% most expensive treatments)
-- Uses PERCENT_RANK for a data-driven top-1% cutoff, independent
-- of the z-score flag already stored on the table.
-- =====================================================
WITH ranked AS (
    SELECT
        treatment_id,
        treatment_type,
        cost,
        PERCENT_RANK() OVER (ORDER BY cost DESC) AS pct_rank
    FROM fact_treatment
    WHERE cost IS NOT NULL
)
SELECT
    treatment_id,
    treatment_type,
    cost
FROM ranked
WHERE pct_rank <= 0.01
ORDER BY cost DESC;


-- =====================================================
-- 10. Cohort analysis: signup month vs treatment frequency
-- NOTE: source data has no explicit patient "signup" date.
-- Each patient's cohort is defined as the month of their
-- FIRST appointment, which is the standard proxy used when
-- no registration date exists.
-- =====================================================
WITH patient_cohort AS (
    SELECT
        patient_id,
        DATE_TRUNC('month', MIN(start_time)) AS cohort_month
    FROM dim_appointment
    WHERE start_time IS NOT NULL
    GROUP BY patient_id
),
patient_treatment_counts AS (
    SELECT
        a.patient_id,
        COUNT(t.treatment_id) AS treatment_count
    FROM dim_appointment a
    JOIN fact_treatment t ON t.appointment_id = a.appointment_id
    GROUP BY a.patient_id
)
SELECT
    pc.cohort_month,
    COUNT(DISTINCT pc.patient_id) AS cohort_size,
    ROUND(AVG(COALESCE(ptc.treatment_count, 0)), 2) AS avg_treatments_per_patient
FROM patient_cohort pc
LEFT JOIN patient_treatment_counts ptc ON ptc.patient_id = pc.patient_id
GROUP BY pc.cohort_month
ORDER BY pc.cohort_month;