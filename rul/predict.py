from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from rul.features import build_rul_features

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "rul_regressor.joblib"


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("RUL model missing. Run: python -m rul.train")
    return joblib.load(MODEL_PATH)


def predict_rul(history: list[dict], current: dict):
    model = load_model()
    feature_vector = build_rul_features(history, current)
    prediction = float(model.predict([feature_vector])[0])
    trees = model.estimators_
    tree_preds = [float(tree.predict([feature_vector])[0]) for tree in trees]
    std = float(np.std(tree_preds)) if tree_preds else 0.0
    return {
        "predicted_rul_minutes": max(0.0, prediction),
        "confidence_band_minutes": max(5.0, std),
        "driving_channel": "oil_pressure" if abs(current.get("oil_pressure_deviation_pct", 0.0)) > abs(current.get("vibration_deviation_pct", 0.0)) else "vibration",
        "model_version": "random_forest_v1",
    }
