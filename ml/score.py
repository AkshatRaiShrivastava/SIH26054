from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
from sklearn.ensemble import IsolationForest

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True, parents=True)
MODEL_PATH = MODEL_DIR / "isolation_forest.joblib"
FEATURE_PATH = MODEL_DIR / "feature_list.json"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"

DEFAULT_THRESHOLD = 0.02


def ensure_model():
    if not MODEL_PATH.exists():
        model = IsolationForest(contamination=0.02, random_state=42)
        joblib.dump(model, MODEL_PATH)
        FEATURE_PATH.write_text(json.dumps(["rpm", "cht_c", "egt_c", "oil_pressure_kpa", "oil_temperature_c", "fuel_flow_lph", "vibration_mms", "battery_voltage", "rpm_slope", "cht_slope", "egt_slope", "oil_pressure_slope", "oil_temperature_slope", "vibration_slope"]))
        THRESHOLD_PATH.write_text(json.dumps({"contamination": 0.02}))
    return MODEL_PATH


def load_model():
    ensure_model()
    return joblib.load(MODEL_PATH)


def score_anomaly(sample: dict):
    model = load_model()
    feature_values = [
        float(sample.get("rpm", 0.0)),
        float(sample.get("cht_c", 0.0)),
        float(sample.get("egt_c", 0.0)),
        float(sample.get("oil_pressure_kpa", 0.0)),
        float(sample.get("oil_temperature_c", 0.0)),
        float(sample.get("fuel_flow_lph", 0.0)),
        float(sample.get("vibration_mms", 0.0)),
        float(sample.get("battery_voltage", 0.0)),
    ]
    score = float(model.decision_function([feature_values])[0])
    anomaly = bool(model.predict([feature_values])[0] == -1)
    return max(0.0, -score), anomaly
