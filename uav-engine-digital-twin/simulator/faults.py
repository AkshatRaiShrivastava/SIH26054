"""Deterministic and explainable fault framework.

Faults now modify internal physics parameters of the EngineModel,
simulating true physical degradation rather than just output offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Any


@dataclass
class Fault:
    name: str
    severity: float = 0.0  # 0.0 to 1.0
    enabled: bool = False
    affected_parameter: str = ""  # The parameter in EngineModel to modify
    scaling_factor: float = 1.0   # How severity affects the parameter


class FaultManager:
    """Manages engine degradation and sensor faults.

    Instead of post-processing telemetry, this manager provides modifiers
    that the EngineModel and SensorModel use to alter their behavior.
    """

    def __init__(self) -> None:
        # Physics-based faults (Degradations)
        self.physics_faults: Dict[str, Fault] = {
            "injector_degradation": Fault(
                "injector_degradation", affected_parameter="fuel_efficiency", scaling_factor=-0.2
            ),
            "cooling_degradation": Fault(
                "cooling_degradation", affected_parameter="cooling_efficiency", scaling_factor=-0.5
            ),
            "lubrication_degradation": Fault(
                "lubrication_degradation", affected_parameter="oil_pressure_base", scaling_factor=-0.4
            ),
            "mechanical_wear": Fault(
                "mechanical_wear", affected_parameter="internal_friction", scaling_factor=0.3
            ),
        }

        # Sensor-based faults (Measurement Errors)
        self.sensor_faults: Dict[str, Fault] = {
            "sensor_drift": Fault("sensor_drift"),
            "sensor_bias": Fault("sensor_bias"),
            "sensor_failure": Fault("sensor_failure"),
        }

    def enable(self, name: str, severity: float) -> None:
        fault = self.physics_faults.get(name) or self.sensor_faults.get(name)
        if not fault:
            raise ValueError(f"Unknown fault: {name}")
        fault.enabled = True
        fault.severity = max(0.0, min(1.0, severity))

    def disable(self, name: str) -> None:
        fault = self.physics_faults.get(name) or self.sensor_faults.get(name)
        if not fault:
            raise ValueError(f"Unknown fault: {name}")
        fault.enabled = False

    def active_physics_faults(self) -> Iterable[Fault]:
        return (f for f in self.physics_faults.values() if f.enabled)

    def active_sensor_faults(self) -> Iterable[Fault]:
        return (f for f in self.sensor_faults.values() if f.enabled)

    def get_physics_modifiers(self) -> Dict[str, float]:
        """Calculate multipliers for engine physics parameters.

        Example: if cooling_degradation is 0.5, cooling_efficiency might be multiplied by 0.75.
        """
        modifiers = {
            "fuel_efficiency": 1.0,
            "cooling_efficiency": 1.0,
            "oil_pressure_base": 1.0,
            "internal_friction": 1.0,
        }

        for fault in self.active_physics_faults():
            param = fault.affected_parameter
            if param in modifiers:
                # Modifier = 1.0 + (severity * scaling_factor)
                modifiers[param] += fault.severity * fault.scaling_factor

        return modifiers

    def get_sensor_modifiers(self, sensor_name: str) -> Dict[str, float]:
        """Calculate modifiers for a specific sensor.

        Returns:
            Dict with 'drift_rate', 'bias', 'failure_mode'.
        """
        mods = {"drift_rate": 0.0, "bias": 0.0, "failure_mode": None}

        for fault in self.active_sensor_faults():
            s = fault.severity
            if fault.name == "sensor_drift":
                mods["drift_rate"] += 0.01 * s
            elif fault.name == "sensor_bias":
                mods["bias"] += 5.0 * s
            elif fault.name == "sensor_failure" and s > 0.8:
                mods["failure_mode"] = "dead"

        return mods
