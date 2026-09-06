from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True, parents=True)


def generate_synthetic_degradation_samples(n_samples: int = 250):
    X = []
    y = []
    for i in range(n_samples):
        health = max(0.0, 100.0 - i * 0.22)
        oil = max(-30.0, -1.0 * i * 0.17)
        vib = max(-20.0, -1.0 * i * 0.1)
        cht = max(-25.0, -1.0 * i * 0.14)
        slope = -0.8 - i * 0.02
        rul = max(10.0, 220.0 - i * 0.7)
        X.append([health, oil, vib, cht, slope, max(abs(oil), abs(vib), abs(cht))])
        y.append(rul)
    return np.array(X, dtype=float), np.array(y, dtype=float)


def train_rul_model():
    X, y = generate_synthetic_degradation_samples(300)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_DIR / "rul_regressor.joblib")
    (MODEL_DIR / "feature_list.json").write_text(json.dumps(["health_index", "oil_pressure_deviation_pct", "vibration_deviation_pct", "cht_deviation_pct", "health_slope", "degraded_channel"]))
    return model


if __name__ == "__main__":
    train_rul_model()
    print("RUL regressor trained and saved to rul/models")
