# Data Quality Report

_Generated: 2026-07-26 23:18:56_

## Source Row Counts

- **patients**: 1100 rows
- **appointments**: 5500 rows
- **treatments**: 7500 rows

## Validation Results

### appointments

- **appointments.null_values** — patient_id: 288
- **appointments.duplicate_appointment_id** — 265 duplicate rows across 110 distinct IDs
- **appointments.orphan_patient_id** — 559 orphan rows (sample IDs: [95.0, 1175.0, 1196.0, 229.0, 1170.0, 1128.0, 1158.0, 1069.0, 1193.0, 1159.0])
- **appointments.invalid_literal_end_time** — 288 invalid rows

### patients

- **patients.null_values** — patient_name: 57, gender: 344
- **patients.duplicate_patient_id** — 60 duplicate rows across 26 distinct IDs
- **patients.invalid_literal_dob** — 45 invalid rows

### treatments

- **treatments.null_values** — duration_minutes: 392, cost: 368
- **treatments.duplicate_treatment_id** — 337 duplicate rows across 125 distinct IDs
- **treatments.orphan_appointment_id** — 330 orphan rows (sample IDs: [4075, 2627, 5511, 5539, 3822, 2188, 2513, 5268, 5536, 5552])
