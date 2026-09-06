from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from simulator.signal_model import simulate_tick

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True, parents=True)


def generate_healthy_samples(n_samples: int = 200):
    samples = []
    prev = {}
    for i in range(n_samples):
        tick = simulate_tick(float(i), prev, "normal", 100.0, 0.0)
        prev = tick
        samples.append({
            "rpm": tick["rpm"],
            "cht_c": tick["cht_c"],
            "egt_c": tick["egt_c"],
            "oil_pressure_kpa": tick["oil_pressure_kpa"],
            "oil_temperature_c": tick["oil_temperature_c"],
            "fuel_flow_lph": tick["fuel_flow_lph"],
            "vibration_mms": tick["vibration_mms"],
            "battery_voltage": tick["battery_voltage"],
        })
    return samples


def train_model():
    training = generate_healthy_samples(250)
    X = np.array([[
        s["rpm"], s["cht_c"], s["egt_c"], s["oil_pressure_kpa"], s["oil_temperature_c"], s["fuel_flow_lph"], s["vibration_mms"], s["battery_voltage"],
    ] for s in training], dtype=float)
    model = IsolationForest(contamination=0.02, random_state=42)
    model.fit(X)
    joblib.dump(model, MODEL_DIR / "isolation_forest.joblib")
    (MODEL_DIR / "feature_list.json").write_text(json.dumps(["rpm", "cht_c", "egt_c", "oil_pressure_kpa", "oil_temperature_c", "fuel_flow_lph", "vibration_mms", "battery_voltage"]))
    (MODEL_DIR / "threshold.json").write_text(json.dumps({"contamination": 0.02}))
    (MODEL_DIR / "healthy_stats.json").write_text(json.dumps({"samples": len(training)}))
    return model


if __name__ == "__main__":
    train_model()
    print("Isolation Forest trained and saved to ml/models")
