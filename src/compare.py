"""
Before/after comparison utilities.
- save_processed_data(): writes the cleaned DataFrames to data/processed/
  so raw and processed data can be diffed/inspected side by side.
- generate_comparison_report(): builds a markdown report comparing raw vs
  processed row counts and null counts.
"""

import os
from datetime import datetime
import pandas as pd

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "processed")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")


# --------------------------------------------------
# Save cleaned data to data/processed/
# --------------------------------------------------
def save_processed_data(transformed_data: dict) -> dict:
    """
    Write the cleaned patients/appointments/treatments DataFrames to
    data/processed/ as CSVs, so the raw and processed versions of the
    data can be opened side by side and diffed directly.

    Returns a dict of {table_name: file_path_written}.
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    paths = {}

    for name in ("patients", "appointments", "treatments"):
        df = transformed_data[name]
        path = os.path.join(PROCESSED_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        paths[name] = path

    return paths


# --------------------------------------------------
# Before / after comparison report
# --------------------------------------------------
def _null_counts(df: pd.DataFrame) -> dict:
    counts = df.isnull().sum()
    return counts[counts > 0].to_dict()


def generate_comparison_report(raw_data: dict, transformed_data: dict) -> str:
    """
    Build a markdown report comparing raw (pre-cleaning) vs processed
    (post-cleaning) data: row counts, rows dropped, and null counts
    before/after for each table.
    """
    lines = []
    lines.append("# Raw vs Processed Data Comparison")
    lines.append("")
    lines.append(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append(
        "This report compares the raw source CSVs (`data/raw/`) against the "
        "cleaned, processed output (`data/processed/`) for the same pipeline run."
    )
    lines.append("")

    lines.append("## Row Counts")
    lines.append("")
    lines.append("| Table | Raw rows | Processed rows | Rows removed | % removed |")
    lines.append("|---|---|---|---|---|")
    for name in ("patients", "appointments", "treatments"):
        raw_count = len(raw_data[name])
        processed_count = len(transformed_data[name])
        removed = raw_count - processed_count
        pct = (removed / raw_count * 100) if raw_count else 0
        lines.append(f"| {name} | {raw_count} | {processed_count} | {removed} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Null Values: Before vs After")
    lines.append("")
    for name in ("patients", "appointments", "treatments"):
        lines.append(f"### {name}")
        lines.append("")
        raw_nulls = _null_counts(raw_data[name])
        processed_nulls = _null_counts(transformed_data[name])

        all_columns = sorted(set(raw_nulls) | set(processed_nulls))
        if not all_columns:
            lines.append("No null values in either raw or processed data.")
            lines.append("")
            continue

        lines.append("| Column | Nulls (raw) | Nulls (processed) |")
        lines.append("|---|---|---|")
        for col in all_columns:
            lines.append(f"| {col} | {raw_nulls.get(col, 0)} | {processed_nulls.get(col, 0)} |")
        lines.append("")

    lines.append(
        "> Columns with zero nulls in the processed column either had no "
        "nulls to begin with, or are one of the columns where this project "
        "chooses to drop incomplete rows entirely (`patient_name`, `gender`, "
        "`dob` on patients; `duration_minutes` on appointments; `cost` and "
        "`duration_minutes` on treatments) rather than keep or impute them."
    )
    lines.append("")

    return "\n".join(lines)


def save_comparison_report(report_text: str, filename: str = "raw_vs_processed_comparison.md") -> str:
    os.makedirs(DOCS_DIR, exist_ok=True)
    path = os.path.join(DOCS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return path


if __name__ == "__main__":
    from validation import extract_all
    from transform import transform_all

    raw = extract_all()
    processed = transform_all(raw["patients"], raw["appointments"], raw["treatments"])

    written = save_processed_data(processed)
    print("Processed CSVs written:")
    for name, path in written.items():
        print(f"  {name}: {path}")

    report = generate_comparison_report(raw, processed)
    report_path = save_comparison_report(report)
    print(f"\nComparison report saved to: {report_path}")