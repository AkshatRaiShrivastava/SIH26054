from __future__ import annotations


def build_rul_features(history: list[dict], current: dict) -> list[float]:
    if not history:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    last = history[-1]
    health_index = current.get("health_index", 100.0)
    slope = current.get("health_index", 100.0) - last.get("health_index", 100.0)
    degraded_channel = max(
        [
            abs(current.get("cht_deviation_pct", 0.0)),
            abs(current.get("egt_deviation_pct", 0.0)),
            abs(current.get("oil_pressure_deviation_pct", 0.0)),
            abs(current.get("oil_temp_deviation_pct", 0.0)),
            abs(current.get("fuel_flow_deviation_pct", 0.0)),
            abs(current.get("vibration_deviation_pct", 0.0)),
        ]
    )
    return [
        float(health_index),
        float(current.get("oil_pressure_deviation_pct", 0.0)),
        float(current.get("vibration_deviation_pct", 0.0)),
        float(current.get("cht_deviation_pct", 0.0)),
        float(slope),
        float(degraded_channel),
    ]
