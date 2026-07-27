"""
Extraction and validation functions for the healthcare ETL pipeline.
Each validation function returns a dict of results so they can be
combined into a single data-quality report.
"""

import pandas as pd
import os
from datetime import datetime

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")


# --------------------------------------------------
# Extract
# --------------------------------------------------
def extract_csv(filename: str) -> pd.DataFrame:
    """Load a CSV from data/raw/ into a DataFrame."""
    path = os.path.join(RAW_DIR, filename)
    df = pd.read_csv(path)
    return df


def extract_all():
    """Load all three source files and return them as a dict."""
    return {
        "patients": extract_csv("patients.csv"),
        "appointments": extract_csv("appointments.csv"),
        "treatments": extract_csv("treatments.csv"),
    }


# --------------------------------------------------
# Null checks
# --------------------------------------------------
def check_nulls(df: pd.DataFrame, table_name: str) -> dict:
    """Return null counts per column."""
    null_counts = df.isnull().sum()
    null_counts = null_counts[null_counts > 0]
    return {
        "table": table_name,
        "check": "null_values",
        "details": null_counts.to_dict(),
    }


# --------------------------------------------------
# Duplicate checks
# --------------------------------------------------
def check_duplicates(df: pd.DataFrame, id_column: str, table_name: str) -> dict:
    """Return count and sample of duplicate IDs in a table."""
    dupe_mask = df[id_column].duplicated(keep=False)
    dupes = df[dupe_mask]
    return {
        "table": table_name,
        "check": f"duplicate_{id_column}",
        "duplicate_row_count": int(dupe_mask.sum()),
        "unique_duplicate_ids": int(dupes[id_column].nunique()),
    }


# --------------------------------------------------
# Orphan checks (referential integrity)
# --------------------------------------------------
def check_orphans(child_df: pd.DataFrame, child_fk: str,
                   parent_df: pd.DataFrame, parent_pk: str,
                   table_name: str) -> dict:
    """
    Find rows in child_df whose foreign key does not exist
    in parent_df's primary key column.
    """
    valid_ids = set(parent_df[parent_pk].dropna().unique())
    child_ids = child_df[child_fk]
    orphan_mask = ~child_ids.isin(valid_ids) & child_ids.notna()
    return {
        "table": table_name,
        "check": f"orphan_{child_fk}",
        "orphan_row_count": int(orphan_mask.sum()),
        "orphan_id_sample": child_ids[orphan_mask].dropna().unique()[:10].tolist(),
    }


# --------------------------------------------------
# Invalid value checks (the "invalid_date" / "invalid_timestamp" strings)
# --------------------------------------------------
def check_invalid_literals(df: pd.DataFrame, column: str,
                            invalid_value: str, table_name: str) -> dict:
    """Count rows where a column contains a known bad literal string."""
    mask = df[column] == invalid_value
    return {
        "table": table_name,
        "check": f"invalid_literal_{column}",
        "invalid_row_count": int(mask.sum()),
    }


# --------------------------------------------------
# dtype check
# --------------------------------------------------
def check_dtypes(df: pd.DataFrame, expected: dict, table_name: str) -> dict:
    """
    Compare actual dtypes against an expected dict, e.g.
    {"patient_id": "int64", "cost": "float64"}
    """
    mismatches = {}
    for col, expected_dtype in expected.items():
        actual_dtype = str(df[col].dtype)
        if actual_dtype != expected_dtype:
            mismatches[col] = {"expected": expected_dtype, "actual": actual_dtype}
    return {
        "table": table_name,
        "check": "dtype_mismatch",
        "details": mismatches,
    }


# --------------------------------------------------
# Run everything and build one report
# --------------------------------------------------
def run_all_validations(data: dict) -> list:
    """
    data: dict with keys 'patients', 'appointments', 'treatments'
    Returns a list of result dicts — one per check.
    """
    patients = data["patients"]
    appointments = data["appointments"]
    treatments = data["treatments"]

    results = []

    # Nulls
    results.append(check_nulls(patients, "patients"))
    results.append(check_nulls(appointments, "appointments"))
    results.append(check_nulls(treatments, "treatments"))

    # Duplicates
    results.append(check_duplicates(patients, "patient_id", "patients"))
    results.append(check_duplicates(appointments, "appointment_id", "appointments"))
    results.append(check_duplicates(treatments, "treatment_id", "treatments"))

    # Orphans
    results.append(check_orphans(appointments, "patient_id", patients, "patient_id", "appointments"))
    results.append(check_orphans(treatments, "appointment_id", appointments, "appointment_id", "treatments"))

    # Invalid literals
    results.append(check_invalid_literals(patients, "dob", "invalid_date", "patients"))
    results.append(check_invalid_literals(appointments, "end_time", "invalid_timestamp", "appointments"))

    return results


# --------------------------------------------------
# Markdown report generation
# --------------------------------------------------
def _format_check_row(result: dict) -> str:
    """Turn one check's result dict into a markdown bullet."""
    table = result["table"]
    check = result["check"]

    if "details" in result:
        details = result["details"]
        if not details:
            return f"- **{table}.{check}** — none found ✅"
        detail_str = ", ".join(f"{k}: {v}" for k, v in details.items())
        return f"- **{table}.{check}** — {detail_str}"

    if "duplicate_row_count" in result:
        return (f"- **{table}.{check}** — {result['duplicate_row_count']} duplicate rows "
                f"across {result['unique_duplicate_ids']} distinct IDs")

    if "orphan_row_count" in result:
        sample = result["orphan_id_sample"]
        return (f"- **{table}.{check}** — {result['orphan_row_count']} orphan rows "
                f"(sample IDs: {sample})")

    if "invalid_row_count" in result:
        return f"- **{table}.{check}** — {result['invalid_row_count']} invalid rows"

    return f"- **{table}.{check}** — {result}"


def generate_markdown_report(results: list, row_counts: dict) -> str:
    """Build the full markdown report as a string."""
    lines = []
    lines.append("# Data Quality Report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append("## Source Row Counts")
    lines.append("")
    for table, count in row_counts.items():
        lines.append(f"- **{table}**: {count} rows")
    lines.append("")
    lines.append("## Validation Results")
    lines.append("")

    # Group results by table for readability
    tables = sorted(set(r["table"] for r in results))
    for table in tables:
        lines.append(f"### {table}")
        lines.append("")
        for r in results:
            if r["table"] == table:
                lines.append(_format_check_row(r))
        lines.append("")

    return "\n".join(lines)


def save_report(report_text: str, filename: str = "data_quality_report.md"):
    os.makedirs(DOCS_DIR, exist_ok=True)
    path = os.path.join(DOCS_DIR, filename)
    with open(path, "w") as f:
        f.write(report_text)
    return path


if __name__ == "__main__":
    data = extract_all()
    report_results = run_all_validations(data)

    for r in report_results:
        print(r)

    row_counts = {name: len(df) for name, df in data.items()}
    markdown = generate_markdown_report(report_results, row_counts)
    saved_path = save_report(markdown)
    print(f"\nData quality report saved to: {saved_path}")