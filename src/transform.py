"""
Transformation functions for the healthcare ETL pipeline.
Each function takes a DataFrame (or several) and returns a new,
cleaned/enriched DataFrame. Kept as pure functions so each one
can be unit tested in isolation.
"""

import pandas as pd
import numpy as np


# --------------------------------------------------
# Cleaning: patients
# --------------------------------------------------
def clean_patients(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Drop duplicate patient_id rows (keep first occurrence)
    - Convert 'invalid_date' strings to real NaT
    - Normalize name whitespace/casing
    """
    df = df.copy()
    df = df.drop_duplicates(subset="patient_id", keep="first")

    df["dob"] = pd.to_datetime(df["dob"], errors="coerce")  # 'invalid_date' -> NaT

    df["patient_name"] = df["patient_name"].str.strip().str.title()

    return df.reset_index(drop=True)


# --------------------------------------------------
# Cleaning: appointments
# --------------------------------------------------
def clean_appointments(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Drop duplicate appointment_id rows (keep first)
    - Convert patient_id to nullable Int64 (was float due to NaNs)
    - Convert 'invalid_timestamp' strings to real NaT
    - Compute visit duration in minutes
    """
    df = df.copy()
    df = df.drop_duplicates(subset="appointment_id", keep="first")

    df["patient_id"] = df["patient_id"].astype("Int64")  # nullable int, keeps NaNs as <NA>

    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", format="mixed")
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce", format="mixed")  # 'invalid_timestamp' -> NaT

    df["duration_minutes"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 60

    return df.reset_index(drop=True)


# --------------------------------------------------
# Cleaning: treatments
# --------------------------------------------------
def clean_treatments(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate treatment_id rows (keep first)."""
    df = df.copy()
    df = df.drop_duplicates(subset="treatment_id", keep="first")
    return df.reset_index(drop=True)


# --------------------------------------------------
# Remove orphan rows (call AFTER cleaning, using cleaned parent tables)
# --------------------------------------------------
def drop_orphans(child_df: pd.DataFrame, child_fk: str,
                  parent_df: pd.DataFrame, parent_pk: str) -> pd.DataFrame:
    """Keep only child rows whose FK exists in the parent table."""
    valid_ids = set(parent_df[parent_pk].dropna().unique())
    mask = child_df[child_fk].isin(valid_ids)
    return child_df[mask].reset_index(drop=True)


# --------------------------------------------------
# Cost aggregation per patient
# --------------------------------------------------
def aggregate_cost_per_patient(appointments: pd.DataFrame, treatments: pd.DataFrame) -> pd.DataFrame:
    """
    Join treatments -> appointments -> patient_id, then sum cost per patient.
    Returns columns: patient_id, total_cost, treatment_count, avg_cost
    """
    merged = treatments.merge(
        appointments[["appointment_id", "patient_id"]],
        on="appointment_id",
        how="inner",
    )
    agg = merged.groupby("patient_id").agg(
        total_cost=("cost", "sum"),
        treatment_count=("treatment_id", "count"),
        avg_cost=("cost", "mean"),
    ).reset_index()
    return agg


# --------------------------------------------------
# Visit frequency (flag frequent visitors)
# --------------------------------------------------
def flag_frequent_visitors(appointments: pd.DataFrame, threshold: int = 5) -> pd.DataFrame:
    """
    Count appointments per patient; flag patients with more than `threshold` visits.
    Returns columns: patient_id, visit_count, is_frequent_visitor
    """
    counts = appointments.groupby("patient_id").size().reset_index(name="visit_count")
    counts["is_frequent_visitor"] = counts["visit_count"] > threshold
    return counts


# --------------------------------------------------
# Cost outlier detection (NumPy, z-score based)
# --------------------------------------------------
def detect_cost_outliers(treatments: pd.DataFrame, z_threshold: float = 3.0) -> pd.DataFrame:
    """
    Flag treatments whose cost is a statistical outlier using z-score.
    Adds a boolean column 'is_cost_outlier'.
    """
    df = treatments.copy()
    costs = df["cost"].to_numpy(dtype=float)

    mean = np.nanmean(costs)
    std = np.nanstd(costs)

    z_scores = np.where(std > 0, (costs - mean) / std, 0)
    df["cost_zscore"] = z_scores
    df["is_cost_outlier"] = np.abs(z_scores) > z_threshold

    return df


# --------------------------------------------------
# Overlapping appointment detection (per doctor)
# --------------------------------------------------
def detect_overlapping_appointments(appointments: pd.DataFrame) -> pd.DataFrame:
    """
    For each doctor, sort appointments by start_time and check whether
    an appointment starts before the previous one (for that doctor) ends.
    Returns the appointments df with an added 'overlaps_previous' column.
    """
    df = appointments.copy()
    df = df.sort_values(["doctor_id", "start_time"]).reset_index(drop=True)

    df["prev_end_time"] = df.groupby("doctor_id")["end_time"].shift(1)
    df["overlaps_previous"] = df["start_time"] < df["prev_end_time"]
    df["overlaps_previous"] = df["overlaps_previous"].fillna(False)

    return df.drop(columns=["prev_end_time"])


# --------------------------------------------------
# Monthly aggregation
# --------------------------------------------------
def monthly_visit_summary(appointments: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate appointment counts by month.
    Returns columns: month, appointment_count
    """
    df = appointments.copy()
    df["month"] = df["start_time"].dt.to_period("M").astype(str)
    summary = df.groupby("month").size().reset_index(name="appointment_count")
    return summary.sort_values("month").reset_index(drop=True)


# --------------------------------------------------
# Full transform pipeline (convenience wrapper)
# --------------------------------------------------
def transform_all(patients: pd.DataFrame, appointments: pd.DataFrame,
                   treatments: pd.DataFrame) -> dict:
    """
    Run the full clean -> drop orphans -> enrich sequence.
    Returns a dict of all resulting DataFrames.
    """
    clean_pat = clean_patients(patients)
    clean_appt = clean_appointments(appointments)
    clean_treat = clean_treatments(treatments)

    appt_no_orphans = drop_orphans(clean_appt, "patient_id", clean_pat, "patient_id")
    treat_no_orphans = drop_orphans(clean_treat, "appointment_id", appt_no_orphans, "appointment_id")

    cost_per_patient = aggregate_cost_per_patient(appt_no_orphans, treat_no_orphans)
    frequent_visitors = flag_frequent_visitors(appt_no_orphans)
    treat_with_outliers = detect_cost_outliers(treat_no_orphans)
    appt_with_overlaps = detect_overlapping_appointments(appt_no_orphans)
    monthly_summary = monthly_visit_summary(appt_no_orphans)

    return {
        "patients": clean_pat,
        "appointments": appt_with_overlaps,
        "treatments": treat_with_outliers,
        "cost_per_patient": cost_per_patient,
        "frequent_visitors": frequent_visitors,
        "monthly_summary": monthly_summary,
    }


if __name__ == "__main__":
    from validation import extract_all

    data = extract_all()
    result = transform_all(data["patients"], data["appointments"], data["treatments"])

    print("Cleaned patients:", len(result["patients"]))
    print("Cleaned appointments (no orphans):", len(result["appointments"]))
    print("Cleaned treatments (no orphans):", len(result["treatments"]))
    print("\nCost per patient (head):")
    print(result["cost_per_patient"].head())
    print("\nCost outliers found:", result["treatments"]["is_cost_outlier"].sum())
    print("\nOverlapping appointments found:", result["appointments"]["overlaps_previous"].sum())
    print("\nMonthly summary:")
    print(result["monthly_summary"].head())
