"""
Unit tests for the healthcare ETL pipeline.
Run with: pytest tests/test_etl.py -v
"""

import sys
import os
import pandas as pd
import numpy as np
import pytest

# Allow imports from src/ without needing to install the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from validation import check_duplicates, check_orphans, check_nulls
from transform import (
    clean_appointments,
    aggregate_cost_per_patient,
    detect_cost_outliers,
    flag_frequent_visitors,
    compute_summary_statistics,
)


# --------------------------------------------------
# Duration calculation
# --------------------------------------------------
def test_appointment_duration_calculated_correctly():
    df = pd.DataFrame({
        "appointment_id": [1, 2],
        "patient_id": [10, 20],
        "doctor_id": [1, 1],
        "start_time": ["2026-01-01 09:00:00", "2026-01-01 10:00:00"],
        "end_time": ["2026-01-01 09:30:00", "2026-01-01 10:45:00"],
    })
    cleaned = clean_appointments(df)
    assert cleaned.loc[0, "duration_minutes"] == pytest.approx(30.0)
    assert cleaned.loc[1, "duration_minutes"] == pytest.approx(45.0)


def test_appointment_duration_is_nan_for_invalid_timestamp():
    df = pd.DataFrame({
        "appointment_id": [1],
        "patient_id": [10],
        "doctor_id": [1],
        "start_time": ["2026-01-01 09:00:00"],
        "end_time": ["invalid_timestamp"],
    })
    cleaned = clean_appointments(df)
    assert pd.isna(cleaned.loc[0, "duration_minutes"])


# --------------------------------------------------
# Cost aggregation
# --------------------------------------------------
def test_cost_aggregation_sums_correctly_per_patient():
    appointments = pd.DataFrame({
        "appointment_id": [1, 2, 3],
        "patient_id": [100, 100, 200],
    })
    treatments = pd.DataFrame({
        "treatment_id": [1, 2, 3],
        "appointment_id": [1, 2, 3],
        "cost": [50.0, 75.0, 200.0],
    })
    result = aggregate_cost_per_patient(appointments, treatments)

    patient_100 = result[result["patient_id"] == 100].iloc[0]
    assert patient_100["total_cost"] == pytest.approx(125.0)
    assert patient_100["treatment_count"] == 2

    patient_200 = result[result["patient_id"] == 200].iloc[0]
    assert patient_200["total_cost"] == pytest.approx(200.0)
    assert patient_200["treatment_count"] == 1


def test_cost_aggregation_excludes_treatments_with_no_matching_appointment():
    appointments = pd.DataFrame({
        "appointment_id": [1],
        "patient_id": [100],
    })
    treatments = pd.DataFrame({
        "treatment_id": [1, 2],
        "appointment_id": [1, 999],  # 999 has no matching appointment
        "cost": [50.0, 9999.0],
    })
    result = aggregate_cost_per_patient(appointments, treatments)
    assert len(result) == 1
    assert result.iloc[0]["total_cost"] == pytest.approx(50.0)


# --------------------------------------------------
# Duplicate detection
# --------------------------------------------------
def test_duplicate_detection_counts_correctly():
    df = pd.DataFrame({
        "patient_id": [1, 2, 2, 3, 3, 3],
        "patient_name": ["A", "B", "B2", "C", "C2", "C3"],
    })
    result = check_duplicates(df, "patient_id", "patients")
    assert result["duplicate_row_count"] == 5  # all rows except id=1
    assert result["unique_duplicate_ids"] == 2  # ids 2 and 3


def test_duplicate_detection_returns_zero_when_no_duplicates():
    df = pd.DataFrame({"patient_id": [1, 2, 3]})
    result = check_duplicates(df, "patient_id", "patients")
    assert result["duplicate_row_count"] == 0
    assert result["unique_duplicate_ids"] == 0


# --------------------------------------------------
# Orphan detection
# --------------------------------------------------
def test_orphan_detection_finds_missing_parent_ids():
    parent = pd.DataFrame({"patient_id": [1, 2, 3]})
    child = pd.DataFrame({"patient_id": [1, 2, 99, 100]})
    result = check_orphans(child, "patient_id", parent, "patient_id", "appointments")
    assert result["orphan_row_count"] == 2
    assert set(result["orphan_id_sample"]) == {99, 100}


def test_orphan_detection_ignores_nulls():
    parent = pd.DataFrame({"patient_id": [1, 2]})
    child = pd.DataFrame({"patient_id": [1, np.nan, 99]})
    result = check_orphans(child, "patient_id", parent, "patient_id", "appointments")
    # only 99 should count as orphan; the NaN is a separate "null" issue, not an orphan
    assert result["orphan_row_count"] == 1


# --------------------------------------------------
# Null detection
# --------------------------------------------------
def test_null_detection_counts_per_column():
    df = pd.DataFrame({
        "patient_name": ["A", None, "C"],
        "gender": [None, None, "F"],
    })
    result = check_nulls(df, "patients")
    assert result["details"]["patient_name"] == 1
    assert result["details"]["gender"] == 2


# --------------------------------------------------
# Outlier detection
# --------------------------------------------------
def test_outlier_detection_flags_extreme_values():
    # Note: with only n=5 points, a single outlier's z-score can never
    # mathematically exceed (n-1)/sqrt(n) ≈ 1.79, since the outlier
    # inflates its own std. Use a threshold below that bound.
    treatments = pd.DataFrame({
        "treatment_id": [1, 2, 3, 4, 5],
        "cost": [100.0, 105.0, 98.0, 102.0, 5_000_000.0],  # last one is a clear outlier
    })
    result = detect_cost_outliers(treatments, z_threshold=1.5)
    assert result.loc[4, "is_cost_outlier"] == True
    assert result.loc[0, "is_cost_outlier"] == False


# --------------------------------------------------
# Frequent visitor flagging
# --------------------------------------------------
def test_frequent_visitor_flagging():
    appointments = pd.DataFrame({
        "patient_id": [1, 1, 1, 1, 1, 1, 2],  # patient 1 has 6 visits, patient 2 has 1
    })
    result = flag_frequent_visitors(appointments, threshold=5)
    patient_1 = result[result["patient_id"] == 1].iloc[0]
    patient_2 = result[result["patient_id"] == 2].iloc[0]
    assert patient_1["is_frequent_visitor"] == True
    assert patient_2["is_frequent_visitor"] == False


# --------------------------------------------------
# Summary statistics
# --------------------------------------------------
def test_summary_statistics_computes_correct_mean_median_stddev():
    appointments = pd.DataFrame({
        "duration_minutes": [10.0, 20.0, 30.0],
    })
    treatments = pd.DataFrame({
        "cost": [100.0, 200.0, 300.0],
        "duration_minutes": [5.0, 15.0, 25.0],
    })
    stats = compute_summary_statistics(appointments, treatments)

    assert stats["cost"]["mean"] == pytest.approx(200.0)
    assert stats["cost"]["median"] == pytest.approx(200.0)
    assert stats["cost"]["count"] == 3

    assert stats["treatment_duration_minutes"]["mean"] == pytest.approx(15.0)
    assert stats["appointment_duration_minutes"]["mean"] == pytest.approx(20.0)


def test_summary_statistics_ignores_nulls():
    appointments = pd.DataFrame({"duration_minutes": [10.0, None, 30.0]})
    treatments = pd.DataFrame({
        "cost": [100.0, None, 300.0],
        "duration_minutes": [5.0, None, 25.0],
    })
    stats = compute_summary_statistics(appointments, treatments)

    # nulls should be dropped, not treated as zero
    assert stats["cost"]["count"] == 2
    assert stats["cost"]["mean"] == pytest.approx(200.0)


def test_summary_statistics_handles_all_null_column():
    appointments = pd.DataFrame({"duration_minutes": [None, None]})
    treatments = pd.DataFrame({"cost": [None, None], "duration_minutes": [None, None]})
    stats = compute_summary_statistics(appointments, treatments)

    assert stats["cost"]["count"] == 0
    assert stats["cost"]["mean"] is None