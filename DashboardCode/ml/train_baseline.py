"""Train a simple anomaly detector on telemetry data.

Creates an IsolationForest model from telemetry of non-fault flights
and saves it to Code/ml/models/anomaly_iforest.pkl

Usage:
    python -m ml.train_baseline --db-path ../digital_twin.db --out models/anomaly_iforest.pkl
"""
import argparse
import os
import pickle
import sqlite3

import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest


FEATURES = [
    "rpm",
    "cht_c",
    "egt_c",
    "oil_temp_c",
    "oil_pressure_psi",
    "fuel_flow_lph",
    "vibration_g",
    "battery_v",
    "afr",
    "humidity_pct",
    "altitude_m",
    "ambient_temp_c",
]


def load_telemetry(conn: sqlite3.Connection) -> pd.DataFrame:
    q = "SELECT flight_id, mission_time_s, timestamp, " + ", ".join(FEATURES) + " FROM telemetry"
    df = pd.read_sql_query(q, conn)
    return df


def main():
    parser = argparse.ArgumentParser(description="Train anomaly detector on telemetry.")
    parser.add_argument("--db-path", default="digital_twin.db", help="Path to SQLite DB")
    parser.add_argument("--out", default="Code/ml/models/anomaly_iforest.pkl", help="Output model path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    conn = sqlite3.connect(args.db_path)
    df = load_telemetry(conn)
    conn.close()

    # Drop rows with NaNs and use all telemetry as baseline (ideally filter only normal flights)
    df = df.dropna(subset=FEATURES)
    X = df[FEATURES].values

    # Simple scaler (mean/std)
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-9
    Xs = (X - mean) / std

    print(f"Training IsolationForest on {Xs.shape[0]} samples and {Xs.shape[1]} features")

    clf = IsolationForest(n_estimators=200, contamination=0.01, random_state=42)
    clf.fit(Xs)

    model = {"clf": clf, "mean": mean, "std": std, "features": FEATURES}

    with open(args.out, "wb") as fh:
        pickle.dump(model, fh)

    print(f"Model saved: {args.out}")


if __name__ == "__main__":
    main()
