"""
etl_pipeline.py
----------------
Demonstrates a multi-source ETL pattern: consolidating data from two systems
with different schemas (an "operations" export and a "vendor billing" export)
into a single, clean, analysis-ready table.

This mirrors a common real-world pattern in operational analytics: source
systems rarely share consistent keys or column names, so the ETL layer has
to standardise, validate, and join before any reporting/BI tool can use it.

Usage:
    python etl_pipeline.py
"""

import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def extract(path: str) -> pd.DataFrame:
    """Load a CSV source and log basic shape info."""
    df = pd.read_csv(path)
    logger.info(f"Extracted {len(df)} rows from {os.path.basename(path)}")
    return df


def standardise_ops(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardise the operations source."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"station_id": "station"})

    # Derived field: on-time performance percentage
    df["otp_pct"] = (df["on_time_flights"] / df["flights_handled"] * 100).round(2)

    # Basic data quality guard: flights_handled should never be 0 or negative
    bad_rows = df[df["flights_handled"] <= 0]
    if len(bad_rows) > 0:
        logger.warning(f"Dropping {len(bad_rows)} ops rows with invalid flight counts")
        df = df[df["flights_handled"] > 0]

    return df


def standardise_billing(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardise the vendor billing source."""
    df = df.copy()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df = df.rename(columns={"invoice_date": "date", "station_code": "station"})

    # Flag and quantify billing discrepancies for downstream KPI use
    flagged = df[df["discrepancy_flag"] == 1]
    logger.info(f"{len(flagged)} of {len(df)} billing rows flagged as discrepancies "
                f"({len(flagged) / len(df) * 100:.1f}%)")

    return df


def aggregate_daily_to_station_level(ops_df: pd.DataFrame, billing_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate both sources to station-level summaries and join into one table.
    This is the step that lets two differently-shaped sources become one
    analysis-ready dataset.
    """
    ops_summary = (
        ops_df.groupby("station")
        .agg(
            total_flights=("flights_handled", "sum"),
            avg_otp_pct=("otp_pct", "mean"),
            avg_turnaround_minutes=("avg_turnaround_minutes", "mean"),
        )
        .reset_index()
    )

    billing_summary = (
        billing_df.groupby("station")
        .agg(
            total_billed_usd=("billed_amount_usd", "sum"),
            discrepancy_count=("discrepancy_flag", "sum"),
            invoice_count=("discrepancy_flag", "count"),
        )
        .reset_index()
    )
    billing_summary["billing_accuracy_pct"] = (
        (1 - billing_summary["discrepancy_count"] / billing_summary["invoice_count"]) * 100
    ).round(2)

    merged = ops_summary.merge(billing_summary, on="station", how="inner")
    logger.info(f"Merged dataset: {len(merged)} stations with complete ops + billing data")

    return merged


def load(df: pd.DataFrame, path: str):
    """Write the final consolidated table to disk."""
    df.to_csv(path, index=False)
    logger.info(f"Wrote consolidated output -> {os.path.basename(path)} ({len(df)} rows)")


def run_pipeline():
    logger.info("Starting ETL pipeline...")

    ops_raw = extract(os.path.join(DATA_DIR, "ops_source.csv"))
    billing_raw = extract(os.path.join(DATA_DIR, "billing_source.csv"))

    ops_clean = standardise_ops(ops_raw)
    billing_clean = standardise_billing(billing_raw)

    consolidated = aggregate_daily_to_station_level(ops_clean, billing_clean)

    load(consolidated, os.path.join(DATA_DIR, "consolidated_station_summary.csv"))

    logger.info("ETL pipeline complete.")
    return consolidated


if __name__ == "__main__":
    result = run_pipeline()
    print("\nPreview of consolidated output:\n")
    print(result.head(10).to_string(index=False))
