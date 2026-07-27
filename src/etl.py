"""
HealthcareETL: orchestrates the pipeline end to end.
This class does NOT contain business logic itself — it calls the
already-tested functions in validation.py and transform.py, and
tracks metrics/logging around each stage.
"""

import logging
from datetime import datetime

from validation import extract_all, run_all_validations, generate_markdown_report, save_report
from transform import transform_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("HealthcareETL")


class HealthcareETL:
    """Orchestrates extract -> validate -> transform -> enrich -> load."""

    def __init__(self):
        self.raw_data = {}
        self.validation_results = []
        self.transformed_data = {}
        self.metrics = {
            "started_at": None,
            "finished_at": None,
            "rows_in": {},
            "rows_out": {},
            "invalid_records": {},
        }

    # ----------------------------------------
    def extract(self):
        logger.info("Extracting source CSVs...")
        self.raw_data = extract_all()
        for name, df in self.raw_data.items():
            self.metrics["rows_in"][name] = len(df)
            logger.info(f"  {name}: {len(df)} rows loaded")
        return self.raw_data

    # ----------------------------------------
    def validate(self):
        logger.info("Running validation checks...")
        self.validation_results = run_all_validations(self.raw_data)

        for r in self.validation_results:
            if "orphan_row_count" in r:
                self.metrics["invalid_records"][f"{r['table']}.{r['check']}"] = r["orphan_row_count"]
            elif "duplicate_row_count" in r:
                self.metrics["invalid_records"][f"{r['table']}.{r['check']}"] = r["duplicate_row_count"]
            elif "invalid_row_count" in r:
                self.metrics["invalid_records"][f"{r['table']}.{r['check']}"] = r["invalid_row_count"]

        row_counts = {name: len(df) for name, df in self.raw_data.items()}
        report_md = generate_markdown_report(self.validation_results, row_counts)
        path = save_report(report_md)
        logger.info(f"  Data quality report saved to {path}")

        return self.validation_results

    # ----------------------------------------
    def transform(self):
        logger.info("Transforming data (cleaning, dropping orphans, enriching)...")
        self.transformed_data = transform_all(
            self.raw_data["patients"],
            self.raw_data["appointments"],
            self.raw_data["treatments"],
        )
        for name in ("patients", "appointments", "treatments"):
            rows = len(self.transformed_data[name])
            self.metrics["rows_out"][name] = rows
            logger.info(f"  {name}: {rows} rows after cleaning")
        return self.transformed_data

    # ----------------------------------------
    def enrich(self):
        """
        Placeholder hook for any additional enrichment beyond transform_all
        (e.g. joining doctor names, adding derived categorical columns).
        transform_all() already computes cost_per_patient, frequent_visitors,
        and monthly_summary, so this stays intentionally light for now.
        """
        logger.info("Enrichment step (using outputs already computed in transform)...")
        return self.transformed_data

    # ----------------------------------------
    def load(self):
        """
        Placeholder for Step 8 — will write self.transformed_data into
        Postgres via SQLAlchemy once the DDL (sql/ddl.sql) is in place.
        """
        logger.info("Load step not implemented yet — coming in Step 8.")

    # ----------------------------------------
    def run(self):
        self.metrics["started_at"] = datetime.now().isoformat()
        logger.info("=== HealthcareETL pipeline starting ===")

        self.extract()
        self.validate()
        self.transform()
        self.enrich()
        self.load()

        self.metrics["finished_at"] = datetime.now().isoformat()
        logger.info("=== HealthcareETL pipeline finished ===")
        logger.info(f"Metrics: {self.metrics}")
        return self.metrics


if __name__ == "__main__":
    etl = HealthcareETL()
    etl.run()