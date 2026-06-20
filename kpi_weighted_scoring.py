"""
kpi_weighted_scoring.py
-------------------------
Demonstrates a weighted multi-metric KPI scoring model — the same pattern
used in real-world vendor/station performance scorecards where multiple
KPIs (each with different business importance) are combined into a single
performance score, which then drives incentive/penalty outcomes.

This is a generalised, synthetic-data version of a pattern commonly used
in operational analytics: e.g. scoring 100+ business units across several
weighted metrics to produce a single comparable performance index.

Usage:
    python kpi_weighted_scoring.py
    (run etl_pipeline.py first to generate consolidated_station_summary.csv)
"""

import pandas as pd
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load_inputs():
    """Load the consolidated station summary and the SLA/weighting reference table."""
    summary_path = os.path.join(DATA_DIR, "consolidated_station_summary.csv")
    sla_path = os.path.join(DATA_DIR, "sla_targets.csv")

    if not os.path.exists(summary_path):
        raise FileNotFoundError(
            "consolidated_station_summary.csv not found. Run etl_pipeline.py first."
        )

    summary = pd.read_csv(summary_path)
    sla = pd.read_csv(sla_path).rename(columns={"station_id": "station"})

    merged = summary.merge(sla, on="station", how="inner")
    logger.info(f"Loaded {len(merged)} stations with KPI + weighting data")
    return merged


def normalise_metric(series: pd.Series, target: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """
    Convert a raw metric into a 0-100 'performance vs target' score.
    Scores above 100 mean the station beat its target; below 100 means it missed.
    """
    if higher_is_better:
        score = (series / target) * 100
    else:
        # for metrics where lower is better (e.g. turnaround minutes), invert the ratio
        score = (target / series) * 100
    return score.clip(lower=0, upper=150)  # cap extreme outliers for readability


def calculate_weighted_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combine three independently-weighted KPIs into a single weighted performance score:
      1. On-time performance (vs target)   - higher is better
      2. Turnaround time (vs target)        - lower is better
      3. Billing accuracy (vs 100% target)  - higher is better

    Each station's weights come from the SLA reference table, mirroring a
    real scorecard where different metrics can carry different importance
    per business unit or contract.
    """
    df = df.copy()

    df["otp_score"] = normalise_metric(df["avg_otp_pct"], df["otp_target_pct"], higher_is_better=True)
    df["turnaround_score"] = normalise_metric(
        df["avg_turnaround_minutes"], df["turnaround_target_minutes"], higher_is_better=False
    )
    df["billing_score"] = normalise_metric(df["billing_accuracy_pct"], pd.Series([100] * len(df)), higher_is_better=True)

    df["weighted_score"] = (
        df["otp_score"] * df["weight_otp"]
        + df["turnaround_score"] * df["weight_turnaround"]
        + df["billing_score"] * df["weight_billing_accuracy"]
    ).round(2)

    return df


def assign_incentive_penalty(df: pd.DataFrame, bonus_threshold: float = 100.0, penalty_threshold: float = 85.0) -> pd.DataFrame:
    """
    Translate the weighted score into a business outcome:
    bonus, neutral, or penalty — mirroring how a scorecard model feeds
    directly into financial outcomes for vendors/stations.
    """
    df = df.copy()

    def classify(score):
        if score >= bonus_threshold:
            return "Bonus"
        elif score < penalty_threshold:
            return "Penalty"
        return "Neutral"

    df["outcome"] = df["weighted_score"].apply(classify)
    return df


def run_scoring():
    logger.info("Starting weighted KPI scoring model...")

    data = load_inputs()
    scored = calculate_weighted_score(data)
    final = assign_incentive_penalty(scored)

    output_cols = [
        "station", "otp_score", "turnaround_score", "billing_score",
        "weighted_score", "outcome"
    ]
    result = final[output_cols].sort_values("weighted_score", ascending=False)

    output_path = os.path.join(DATA_DIR, "station_performance_scorecard.csv")
    result.to_csv(output_path, index=False)
    logger.info(f"Wrote scorecard -> {os.path.basename(output_path)} ({len(result)} stations)")

    outcome_counts = result["outcome"].value_counts().to_dict()
    logger.info(f"Outcome distribution: {outcome_counts}")

    return result


if __name__ == "__main__":
    scorecard = run_scoring()
    print("\nTop 5 performing stations:\n")
    print(scorecard.head(5).to_string(index=False))
    print("\nBottom 5 performing stations:\n")
    print(scorecard.tail(5).to_string(index=False))
