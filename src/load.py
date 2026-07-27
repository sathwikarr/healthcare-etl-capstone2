"""
Load functions: write transformed DataFrames into the Postgres star schema.
Uses INSERT ... ON CONFLICT DO UPDATE (upsert) so re-running the pipeline
is safe and idempotent.
"""

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sanitize_records(df: pd.DataFrame) -> list:
    """
    Convert a DataFrame to a list of dicts suitable for psycopg2 params.
    Replaces NaN / NaT / pd.NA with None, since psycopg2 doesn't understand
    pandas' null sentinels.
    """
    clean_df = df.astype(object).where(pd.notnull(df), None)
    return clean_df.to_dict(orient="records")


def _upsert_dataframe(df: pd.DataFrame, table: str, pk, engine: Engine,
                       update_columns: list = None):
    """
    Generic upsert: insert rows, and on primary-key conflict, update
    the specified columns (or all non-PK columns if not given).
    Executes in batches for reasonable performance on larger tables.

    pk: a single column name (str) or a list of column names for a
    composite primary key (e.g. ["treatment_id", "treatment_month"]
    for the partitioned fact_treatment table).
    """
    if df.empty:
        return 0

    pk_columns = [pk] if isinstance(pk, str) else list(pk)

    columns = list(df.columns)
    if update_columns is None:
        update_columns = [c for c in columns if c not in pk_columns]

    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    pk_list = ", ".join(pk_columns)

    if update_columns:
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)
        conflict_action = f"DO UPDATE SET {update_clause}"
    else:
        # No non-PK columns to update (e.g. dim_doctor has only doctor_id) —
        # just skip the row if it already exists.
        conflict_action = "DO NOTHING"

    sql = text(f"""
        INSERT INTO {table} ({col_list})
        VALUES ({placeholders})
        ON CONFLICT ({pk_list}) {conflict_action}
    """)

    records = _sanitize_records(df)

    with engine.begin() as conn:
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            conn.execute(sql, batch)

    return len(records)


def load_dim_patient(patients: pd.DataFrame, engine: Engine) -> int:
    df = patients[["patient_id", "patient_name", "dob", "gender"]].copy()
    return _upsert_dataframe(df, "dim_patient", "patient_id", engine)


def load_dim_doctor(appointments: pd.DataFrame, engine: Engine) -> int:
    """Doctor dimension is derived from distinct doctor_ids seen in appointments."""
    doctor_ids = appointments["doctor_id"].dropna().unique()
    df = pd.DataFrame({"doctor_id": doctor_ids})
    return _upsert_dataframe(df, "dim_doctor", "doctor_id", engine)


def load_dim_appointment(appointments: pd.DataFrame, engine: Engine) -> int:
    df = appointments[[
        "appointment_id", "patient_id", "doctor_id",
        "start_time", "end_time", "duration_minutes", "overlaps_previous"
    ]].copy()
    return _upsert_dataframe(df, "dim_appointment", "appointment_id", engine)


def load_fact_treatment(treatments: pd.DataFrame, appointments: pd.DataFrame, engine: Engine) -> int:
    """
    fact_treatment is partitioned by month (see sql/ddl.sql), keyed on
    a derived treatment_month column since treatments have no date of
    their own. treatment_month is taken from the parent appointment's
    start_time, truncated to the 1st of the month.
    """
    merged = treatments.merge(
        appointments[["appointment_id", "start_time"]],
        on="appointment_id",
        how="inner",  # orphan treatments were already dropped in transform
    )
    merged["treatment_month"] = merged["start_time"].dt.to_period("M").dt.to_timestamp().dt.date

    df = merged[[
        "treatment_id", "appointment_id", "treatment_type",
        "duration_minutes", "cost", "is_cost_outlier", "cost_zscore", "treatment_month"
    ]].copy()

    return _upsert_dataframe(df, "fact_treatment", ["treatment_id", "treatment_month"], engine)


def load_all(transformed_data: dict, engine: Engine) -> dict:
    """
    Load in dependency order: patients & doctors first (referenced by
    appointments), then appointments (referenced by treatments), then
    treatments last.
    """
    counts = {}
    counts["dim_patient"] = load_dim_patient(transformed_data["patients"], engine)
    counts["dim_doctor"] = load_dim_doctor(transformed_data["appointments"], engine)
    counts["dim_appointment"] = load_dim_appointment(transformed_data["appointments"], engine)
    counts["fact_treatment"] = load_fact_treatment(
        transformed_data["treatments"], transformed_data["appointments"], engine
    )
    return counts


def log_audit_run(metrics: dict, engine: Engine):
    """Write one row per (table, check) combination into etl_audit_log."""
    rows = []
    for table_check, invalid_count in metrics["invalid_records"].items():
        table_name, check_name = table_check.split(".", 1)
        rows.append({
            "run_started_at": metrics["started_at"],
            "run_finished_at": metrics["finished_at"],
            "table_name": table_name,
            "rows_in": metrics["rows_in"].get(table_name),
            "rows_out": metrics["rows_out"].get(table_name),
            "invalid_records": invalid_count,
            "check_name": check_name,
        })

    if not rows:
        return 0

    sql = text("""
        INSERT INTO etl_audit_log
            (run_started_at, run_finished_at, table_name, rows_in, rows_out, invalid_records, check_name)
        VALUES
            (:run_started_at, :run_finished_at, :table_name, :rows_in, :rows_out, :invalid_records, :check_name)
    """)

    with engine.begin() as conn:
        conn.execute(sql, rows)

    return len(rows)