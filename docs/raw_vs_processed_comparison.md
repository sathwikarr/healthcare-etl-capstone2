# Raw vs Processed Data Comparison

_Generated: 2026-07-28 12:32:46_

This report compares the raw source CSVs (`data/raw/`) against the cleaned, processed output (`data/processed/`) for the same pipeline run.

## Row Counts

| Table | Raw rows | Processed rows | Rows removed | % removed |
|---|---|---|---|---|
| patients | 1100 | 646 | 454 | 41.3% |
| appointments | 5500 | 2565 | 2935 | 53.4% |
| treatments | 7500 | 3105 | 4395 | 58.6% |

## Null Values: Before vs After

### patients

| Column | Nulls (raw) | Nulls (processed) |
|---|---|---|
| gender | 364 | 0 |
| patient_name | 53 | 0 |

### appointments

| Column | Nulls (raw) | Nulls (processed) |
|---|---|---|
| patient_id | 258 | 0 |

### treatments

| Column | Nulls (raw) | Nulls (processed) |
|---|---|---|
| cost | 363 | 0 |
| duration_minutes | 370 | 0 |

> Columns with zero nulls in the processed column either had no nulls to begin with, or are one of the columns where this project chooses to drop incomplete rows entirely (`patient_name`, `gender`, `dob` on patients; `duration_minutes` on appointments; `cost` and `duration_minutes` on treatments) rather than keep or impute them.
