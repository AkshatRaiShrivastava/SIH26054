from __future__ import annotations

import os
import time
from typing import Any

from ingestion.decoder import decode_can_message
from physics.atmosphere import ambient_temperature_c
from physics.config import PHYSICS_CONFIG
from physics.deviation import deviation_pct
from physics.expected_values import expected_cht_c, expected_egt_c, expected_fuel_flow_lph, expected_oil_pressure_kpa, expected_oil_temperature_c, expected_vibration_baseline
from ml.score import score_anomaly
from health_index.composite import health_index_score
from rules.fault_signatures import classify_fault


class TelemetryProcessor:
    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.latest_metrics = {}
        self.latest_raw = {}
        self.locked_state = {"history": []}

    def process(self, raw: dict):
        elapsed_s = raw.get("elapsed_s", 0.0)
        phase_id = raw.get("phase_id", 0)
        signal = {
            "rpm": float(raw.get("rpm", 0.0)),
            "cht_c": float(raw.get("cht_c", 0.0)),
            "egt_c": float(raw.get("egt_c", 0.0)),
            "oil_pressure_kpa": float(raw.get("oil_pressure_kpa", 0.0)),
            "oil_temperature_c": float(raw.get("oil_temperature_c", 0.0)),
            "fuel_flow_lph": float(raw.get("fuel_flow_lph", 0.0)),
            "vibration_mms": float(raw.get("vibration_mms", 0.0)),
            "afr": float(raw.get("afr", 14.7)),
            "battery_voltage": float(raw.get("battery_voltage", 13.5)),
            "altitude_m": float(raw.get("altitude_m", 0.0)),
            "ambient_temp_c": float(raw.get("ambient_temp_c", ambient_temperature_c(float(raw.get("altitude_m", 0.0)), PHYSICS_CONFIG.T0_C))),
        }

        self.latest_raw = signal
        phase_id = int(phase_id)
        cht_expected = expected_cht_c(signal["rpm"], signal["altitude_m"], signal["ambient_temp_c"], signal["oil_temperature_c"])
        egt_expected = expected_egt_c(signal["rpm"], signal["ambient_temp_c"], signal["afr"])
        oil_temp_expected = expected_oil_temperature_c(signal["rpm"], signal["oil_temperature_c"], signal["ambient_temp_c"], 50.0)
        oil_pressure_expected = expected_oil_pressure_kpa(signal["rpm"], 50.0)
        fuel_flow_expected = expected_fuel_flow_lph(signal["rpm"], 50.0)
        vib_expected = expected_vibration_baseline(signal["rpm"])

        computed = {
            "mission_id": self.mission_id,
            "timestamp": time.time(),
            "elapsed_s": elapsed_s,
            "phase_id": phase_id,
            "cht_expected": cht_expected,
            "cht_deviation_pct": deviation_pct(signal["cht_c"], cht_expected),
            "egt_expected": egt_expected,
            "egt_deviation_pct": deviation_pct(signal["egt_c"], egt_expected),
            "oil_pressure_expected": oil_pressure_expected,
            "oil_pressure_deviation_pct": deviation_pct(signal["oil_pressure_kpa"], oil_pressure_expected),
            "oil_temp_expected": oil_temp_expected,
            "oil_temp_deviation_pct": deviation_pct(signal["oil_temperature_c"], oil_temp_expected),
            "fuel_flow_expected": fuel_flow_expected,
            "fuel_flow_deviation_pct": deviation_pct(signal["fuel_flow_lph"], fuel_flow_expected),
            "vibration_baseline": vib_expected,
            "vibration_deviation_pct": deviation_pct(signal["vibration_mms"], vib_expected),
        }

        anomaly_score, is_anomaly = score_anomaly(signal)
        computed["anomaly_score"] = anomaly_score
        computed["is_anomaly"] = is_anomaly
        computed["model_version"] = "isolation_forest_v1"
        computed["health_index"] = health_index_score([
            computed["cht_deviation_pct"],
            computed["egt_deviation_pct"],
            computed["oil_pressure_deviation_pct"],
            computed["oil_temp_deviation_pct"],
            computed["fuel_flow_deviation_pct"],
            computed["vibration_deviation_pct"],
        ], anomaly_score)

        fault_alert = None
        if is_anomaly:
            fault_alert = classify_fault(computed)

        payload = {
            "raw": signal,
            "computed": computed,
            "physics": {
                "cht": {
                    "actual": signal["cht_c"],
                    "expected": cht_expected,
                    "residual": signal["cht_c"] - cht_expected,
                    "deviation_pct": computed["cht_deviation_pct"],
                },
                "egt": {
                    "actual": signal["egt_c"],
                    "expected": egt_expected,
                    "residual": signal["egt_c"] - egt_expected,
                    "deviation_pct": computed["egt_deviation_pct"],
                },
            },
            "fault_alert": fault_alert,
            "rul": {"predicted_rul_minutes": None, "confidence_band_minutes": None, "driving_channel": None},
        }
        self.latest_metrics = payload
        return payload
