from __future__ import annotations


def classify_fault(computed: dict):
    deviations = {
        "cht": abs(computed.get("cht_deviation_pct", 0.0)),
        "egt": abs(computed.get("egt_deviation_pct", 0.0)),
        "oil_pressure": abs(computed.get("oil_pressure_deviation_pct", 0.0)),
        "oil_temp": abs(computed.get("oil_temp_deviation_pct", 0.0)),
        "vibration": abs(computed.get("vibration_deviation_pct", 0.0)),
    }
    if deviations["oil_pressure"] > 8 or deviations["oil_temp"] > 6:
        return {
            "fault_category": "lubrication_problem",
            "confidence": "high",
            "driving_features": ["oil_pressure", "oil_temperature", "vibration"],
        }
    if deviations["egt"] > 10 or deviations["cht"] > 9:
        return {
            "fault_category": "injector_abnormality",
            "confidence": "medium",
            "driving_features": ["egt", "cht", "fuel_flow"],
        }
    if deviations["cht"] > 12 or deviations["egt"] > 12:
        return {
            "fault_category": "overheating_trend",
            "confidence": "high",
            "driving_features": ["cht", "egt", "oil_temperature"],
        }
    if deviations["vibration"] > 15:
        return {
            "fault_category": "combustion_instability",
            "confidence": "medium",
            "driving_features": ["vibration", "egt", "rpm"],
        }
    return {
        "fault_category": "electrical_system_issue",
        "confidence": "low",
        "driving_features": ["battery_voltage"],
    }
