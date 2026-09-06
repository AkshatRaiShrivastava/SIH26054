"""Simple inference helpers for the anomaly detector.

Provides functions to load model and score the latest telemetry window for a flight.

Usage (CLI):
    python -m ml.infer --db-path digital_twin.db --flight FL-TEST-001 --model Code/ml/models/anomaly_iforest.pkl
"""
import argparse
import json
import pickle
import sqlite3

import numpy as np
import pandas as pd
from src.core.physics_layer import PhysicsEvaluator

DEFAULT_MODEL = "Code/ml/models/anomaly_iforest.pkl"


def load_model(path: str):
    with open(path, "rb") as fh:
        model = pickle.load(fh)
    return model


def get_latest_window(conn: sqlite3.Connection, flight_id: str, window_size: int = 30) -> pd.DataFrame:
    q = (
        "SELECT mission_time_s, timestamp, rpm, cht_c, egt_c, oil_temp_c, oil_pressure_psi, "
        "fuel_flow_lph, vibration_g, battery_v, afr, humidity_pct, altitude_m, ambient_temp_c, phase "
        "FROM telemetry WHERE flight_id = ? ORDER BY mission_time_s DESC LIMIT ?"
    )
    df = pd.read_sql_query(q, conn, params=(flight_id, window_size))
    return df[::-1]  # return in chronological order


def score_window(df: pd.DataFrame, model: dict) -> float:
    features = model["features"]
    X = df[features].dropna().values
    if X.shape[0] == 0:
        return float("nan")

    mean = model["mean"]
    std = model["std"]
    Xs = (X - mean) / std
    scores = model["clf"].decision_function(Xs)  # higher -> more normal
    # We invert so that higher = more anomalous
    anomaly_score = -np.mean(scores)
    return float(anomaly_score)


def main():
    parser = argparse.ArgumentParser(description="Run anomaly inference for a flight")
    parser.add_argument("--db-path", default="digital_twin.db")
    parser.add_argument("--flight", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--window", type=int, default=30)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    df = get_latest_window(conn, args.flight, args.window)
    conn.close()

    # Integrate Physics Layer: Transform raw telemetry to residuals
    evaluator = PhysicsEvaluator(flight_id=args.flight)
    residual_data = []
    for _, row in df.iterrows():
        expected = evaluator.compute_expected_values(row.to_dict())
        row_devs = {}
        # Use the features the model was trained on (expecting _dev suffix)
        # We need to load the model first to know the features, but we can also use the known list
        # For now, let's load the model first.
        pass

    # Correction: Load model first to get features
    model = load_model(args.model)
    features = model["features"]

    # Compute residuals for each row in the window
    transformed_rows = []
    for _, row in df.iterrows():
        expected = evaluator.compute_expected_values(row.to_dict())
        devs = {}
        for feat in features:
            param = feat.replace("_dev", "")
            actual = row.get(param, 0)
            expected_val = expected.get(param, 0)
            devs[feat] = evaluator.compute_deviation(actual, expected_val)
        transformed_rows.append(devs)

    df_residuals = pd.DataFrame(transformed_rows)
    
    score = score_window(df_residuals, model)

    out = {"flight_id": args.flight, "anomaly_score": score}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
