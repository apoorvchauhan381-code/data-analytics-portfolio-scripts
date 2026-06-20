"""
generate_sample_data.py
------------------------
Generates synthetic multi-source operational data for demo purposes.
Mimics the shape of real-world airline station data (volumes, SLA timestamps,
vendor billing) WITHOUT using any real, confidential, or proprietary data.

Run this first to populate the /data folder before running the other scripts.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

STATIONS = [f"STN{str(i).zfill(3)}" for i in range(1, 31)]  # 30 sample stations
VENDORS = ["VendorA", "VendorB", "VendorC", "VendorD"]

def generate_ops_source():
    """Simulates a raw 'operations system' export — flight handling volumes & delays."""
    rows = []
    start_date = datetime(2026, 1, 1)
    for day in range(60):  # 60 days of data
        date = start_date + timedelta(days=day)
        for station in STATIONS:
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "station_id": station,
                "flights_handled": np.random.randint(5, 80),
                "on_time_flights": None,  # filled below
                "avg_turnaround_minutes": round(np.random.normal(35, 8), 1),
            })
    df = pd.DataFrame(rows)
    # on-time flights as a noisy fraction of flights handled (simulates real OTP variance)
    otp_rate = np.clip(np.random.normal(0.88, 0.07, len(df)), 0.5, 1.0)
    df["on_time_flights"] = (df["flights_handled"] * otp_rate).round().astype(int)
    return df

def generate_billing_source():
    """Simulates a separate 'vendor billing system' export — different shape, different keys."""
    rows = []
    start_date = datetime(2026, 1, 1)
    for day in range(60):
        date = start_date + timedelta(days=day)
        for station in STATIONS:
            vendor = np.random.choice(VENDORS)
            rows.append({
                "invoice_date": date.strftime("%Y-%m-%d"),
                "station_code": station,       # NOTE: different column name than ops source
                "vendor_name": vendor,
                "billed_amount_usd": round(np.random.uniform(800, 6500), 2),
                "discrepancy_flag": np.random.choice([0, 0, 0, 0, 1]),  # ~20% flagged
            })
    return pd.DataFrame(rows)

def generate_sla_targets():
    """Simulates a reference table of per-station SLA targets (used for KPI scoring)."""
    rows = []
    for station in STATIONS:
        rows.append({
            "station_id": station,
            "otp_target_pct": np.random.choice([85, 88, 90, 92]),
            "turnaround_target_minutes": np.random.choice([30, 32, 35, 38]),
            "weight_otp": 0.5,
            "weight_turnaround": 0.3,
            "weight_billing_accuracy": 0.2,
        })
    return pd.DataFrame(rows)

if __name__ == "__main__":
    ops_df = generate_ops_source()
    billing_df = generate_billing_source()
    sla_df = generate_sla_targets()

    ops_df.to_csv(os.path.join(OUTPUT_DIR, "ops_source.csv"), index=False)
    billing_df.to_csv(os.path.join(OUTPUT_DIR, "billing_source.csv"), index=False)
    sla_df.to_csv(os.path.join(OUTPUT_DIR, "sla_targets.csv"), index=False)

    print(f"Generated {len(ops_df)} ops rows -> data/ops_source.csv")
    print(f"Generated {len(billing_df)} billing rows -> data/billing_source.csv")
    print(f"Generated {len(sla_df)} SLA target rows -> data/sla_targets.csv")
    print("\nSample data ready. Run etl_pipeline.py next.")
