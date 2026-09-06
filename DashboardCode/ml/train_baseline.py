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

from src.core.physics_layer import PhysicsEvaluator
from sklearn.ensemble import IsolationForest


RAW_FEATURES = [
    "rpm",
    "cht_c",
    "egt_c",
    "oil_temp_c",
    "oil_pressure_psi",
    "fuel_flow_lph",
    "vibration_g",
    "battery_v",
    "afr",
    "altitude_m",
    "phase",
]

FEATURES = [
    "rpm_dev",
    "cht_c_dev",
    "egt_c_dev",
    "oil_temp_c_dev",
    "oil_pressure_psi_dev",
    "fuel_flow_lph_dev",
    "vibration_g_dev",
    "battery_v_dev",
    "afr_dev",
]


def load_telemetry(conn: sqlite3.Connection) -> pd.DataFrame:
    q = "SELECT flight_id, mission_time_s, timestamp, " + ", ".join(RAW_FEATURES) + " FROM telemetry"
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

    print("Computing physics residuals for training set...")

    # Use a dummy flight_id for the evaluator (it's only used for initialization)
    evaluator = PhysicsEvaluator(flight_id="TRAIN-BASELINE")

    residual_data = []
    for _, row in df.iterrows():
        # Compute expected values using physics layer
        expected = evaluator.compute_expected_values(row.to_dict())

        # Compute residuals for each feature in FEATURES
        row_devs = []
        for feat in FEATURES:
            param = feat.replace("_dev", "")
            actual = row.get(param, 0)
            expected_val = expected.get(param, 0)

            # Use the evaluator's deviation logic (percentage)
            dev = evaluator.compute_deviation(actual, expected_val)
            row_devs.append(dev)

        residual_data.append(row_devs)

    # Create DataFrame from residuals
    X = np.array(residual_data)

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
