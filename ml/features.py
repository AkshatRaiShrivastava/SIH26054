from __future__ import annotations

import json
from pathlib import Path


def build_feature_vector(sample: dict) -> list[float]:
    return [
        float(sample.get("rpm", 0.0)),
        float(sample.get("cht_c", 0.0)),
        float(sample.get("egt_c", 0.0)),
        float(sample.get("oil_pressure_kpa", 0.0)),
        float(sample.get("oil_temperature_c", 0.0)),
        float(sample.get("fuel_flow_lph", 0.0)),
        float(sample.get("vibration_mms", 0.0)),
        float(sample.get("battery_voltage", 0.0)),
    ]


def build_live_feature(sample: dict, rolling_history: list[dict]) -> list[float]:
    features = build_feature_vector(sample)
    if rolling_history:
        recent = rolling_history[-1]
        for key in ["rpm", "cht_c", "egt_c", "oil_pressure_kpa", "oil_temperature_c", "vibration_mms"]:
            current = sample.get(key, 0.0)
            previous = recent.get(key, current)
            slope = current - previous
            features.append(float(slope))
    else:
        features.extend([0.0] * 6)
    return features
