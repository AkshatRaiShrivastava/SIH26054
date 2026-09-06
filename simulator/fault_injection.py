from __future__ import annotations

from simulator.mission_profile import SCENARIO_SPECS


def scenario_details(scenario_name: str):
    return SCENARIO_SPECS.get(scenario_name, SCENARIO_SPECS["normal"])


def fault_severity_for(elapsed_s: float, scenario_name: str) -> float:
    spec = scenario_details(scenario_name)
    if spec.name == "normal":
        return 0.0
    if elapsed_s < spec.onset_s:
        return 0.0
    ramp = min(1.0, (elapsed_s - spec.onset_s) / 900.0)
    return min(1.2, spec.severity + ramp * 0.9)


def build_fault_context(elapsed_s: float, scenario_name: str):
    spec = scenario_details(scenario_name)
    return {
        "fault_name": spec.name,
        "onset_time": spec.onset_s,
        "severity": fault_severity_for(elapsed_s, scenario_name),
        "affected_parameters": [
            "oil_pressure_kpa",
            "oil_temperature_c",
            "vibration_mms",
            "egt_c",
            "cht_c",
            "battery_voltage",
        ],
    }
