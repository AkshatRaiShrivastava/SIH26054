"""Deterministic and explainable fault framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from .telemetry import EngineTelemetry


@dataclass
class Fault:
    name: str
    severity: float = 0.0
    enabled: bool = False

    def clamp(self) -> None:
        self.severity = max(0.0, min(1.0, self.severity))


class FaultManager:
    def __init__(self) -> None:
        self.faults: Dict[str, Fault] = {
            "injector_degradation": Fault("injector_degradation"),
            "overheating": Fault("overheating"),
            "lubrication_problem": Fault("lubrication_problem"),
            "vibration_fault": Fault("vibration_fault"),
            "sensor_drift": Fault("sensor_drift"),
        }

    def enable(self, name: str, severity: float) -> None:
        if name not in self.faults:
            raise ValueError(f"Unknown fault: {name}")
        fault = self.faults[name]
        fault.enabled = True
        fault.severity = max(0.0, min(1.0, severity))

    def disable(self, name: str) -> None:
        if name not in self.faults:
            raise ValueError(f"Unknown fault: {name}")
        self.faults[name].enabled = False

    def active_faults(self) -> Iterable[Fault]:
        return (fault for fault in self.faults.values() if fault.enabled)

    def apply(self, telemetry: EngineTelemetry, baseline_rpm: float) -> EngineTelemetry:
        rpm = telemetry.rpm
        cht_c = telemetry.cht_c
        egt_c = telemetry.egt_c
        oil_pressure_kpa = telemetry.oil_pressure_kpa
        oil_temperature_c = telemetry.oil_temperature_c
        fuel_flow_lph = telemetry.fuel_flow_lph
        vibration_mms = telemetry.vibration_mms
        battery_voltage = telemetry.battery_voltage

        for fault in self.active_faults():
            s = fault.severity
            if fault.name == "injector_degradation":
                fuel_flow_lph *= 1.0 + 0.08 * s
                egt_c += 18.0 * s
                vibration_mms += 0.12 * s
                rpm -= baseline_rpm * 0.02 * s
            elif fault.name == "overheating":
                cht_c += 35.0 * s
                egt_c += 22.0 * s
                rpm -= baseline_rpm * 0.03 * s
            elif fault.name == "lubrication_problem":
                oil_pressure_kpa *= 1.0 - 0.35 * s
                oil_temperature_c += 12.0 * s
                vibration_mms += 0.25 * s
            elif fault.name == "vibration_fault":
                vibration_mms += 0.8 * s
                rpm -= baseline_rpm * 0.01 * s
            elif fault.name == "sensor_drift":
                # Deterministic independent sensor drift for future DT diagnosis.
                cht_c += 4.0 * s
                egt_c -= 6.0 * s
                battery_voltage += 0.4 * s

        return EngineTelemetry(
            rpm=max(0.0, rpm),
            cht_c=max(-40.0, cht_c),
            egt_c=max(-40.0, egt_c),
            oil_pressure_kpa=max(0.0, oil_pressure_kpa),
            oil_temperature_c=max(-40.0, oil_temperature_c),
            fuel_flow_lph=max(0.0, fuel_flow_lph),
            vibration_mms=max(0.0, vibration_mms),
            battery_voltage=max(0.0, battery_voltage),
        )
