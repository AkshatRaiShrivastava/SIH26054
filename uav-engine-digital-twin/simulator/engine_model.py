"""Physically plausible engine behavior model."""

from __future__ import annotations

from dataclasses import dataclass

from .environment import EnvironmentModel
from .telemetry import EngineInputs, EngineTelemetry


@dataclass
class EngineDynamics:
    rpm: float = 1400.0
    cht_c: float = 110.0
    egt_c: float = 500.0
    oil_pressure_kpa: float = 250.0
    oil_temperature_c: float = 70.0
    fuel_flow_lph: float = 10.0
    vibration_mms: float = 0.5
    battery_voltage: float = 27.4


class EngineModel:
    """Synthetic engine model with smooth first-order dynamics."""

    def __init__(self) -> None:
        self.dynamics = EngineDynamics()
        self.environment = EnvironmentModel()

    @staticmethod
    def _lag(current: float, target: float, alpha: float) -> float:
        return current + (target - current) * max(0.0, min(1.0, alpha))

    def step(self, inputs: EngineInputs, dt: float = 0.1) -> EngineTelemetry:
        density_ratio = self.environment.density_ratio(
            inputs.altitude_m, inputs.ambient_temperature_c
        )
        heat_load = self.environment.heat_load_factor(
            inputs.ambient_temperature_c, inputs.altitude_m
        )

        health = max(0.2, min(1.0, inputs.engine_health))
        age_penalty = min(0.22, inputs.engine_age_hours / 5000.0 * 0.22)
        effective_health = max(0.15, health - age_penalty)

        load = max(0.0, min(1.0, inputs.engine_load))
        throttle = max(0.0, min(1.0, inputs.throttle))

        rpm_target = 1400.0 + throttle * 4300.0 * density_ratio * (0.92 + 0.08 * effective_health)
        rpm_target *= 0.90 + 0.20 * load
        rpm_target = max(1100.0, min(5800.0, rpm_target))

        cht_target = 95.0 + load * 60.0 + throttle * 35.0 + (1.0 - density_ratio) * 30.0
        cht_target *= heat_load
        cht_target += (1.0 - effective_health) * 22.0

        egt_target = 430.0 + load * 220.0 + throttle * 130.0 + (1.0 - density_ratio) * 55.0
        egt_target += (1.0 - effective_health) * 28.0

        oil_temp_target = 65.0 + load * 24.0 + throttle * 10.0 + (1.0 - density_ratio) * 10.0
        oil_temp_target += (1.0 - effective_health) * 8.0

        oil_pressure_target = 410.0 + rpm_target * 0.05 + effective_health * 55.0
        oil_pressure_target -= max(0.0, oil_temp_target - 100.0) * 1.6
        oil_pressure_target = max(120.0, min(520.0, oil_pressure_target))

        fuel_flow_target = 4.0 + throttle * 21.0 + load * 8.0
        fuel_flow_target *= 1.0 / max(0.65, density_ratio)
        fuel_flow_target *= 1.0 + (1.0 - effective_health) * 0.09

        vibration_target = 0.35 + load * 0.8 + (1.0 - effective_health) * 1.1 + (1.0 - density_ratio) * 0.15

        battery_target = 27.8 + 0.3 * effective_health - max(0.0, load - 0.8) * 0.4

        alpha = min(1.0, dt * 1.8)
        self.dynamics.rpm = self._lag(self.dynamics.rpm, rpm_target, alpha)
        self.dynamics.cht_c = self._lag(self.dynamics.cht_c, cht_target, dt * 0.9)
        self.dynamics.egt_c = self._lag(self.dynamics.egt_c, egt_target, dt * 0.9)
        self.dynamics.oil_temperature_c = self._lag(self.dynamics.oil_temperature_c, oil_temp_target, dt * 0.7)
        self.dynamics.oil_pressure_kpa = self._lag(self.dynamics.oil_pressure_kpa, oil_pressure_target, dt * 1.2)
        self.dynamics.fuel_flow_lph = self._lag(self.dynamics.fuel_flow_lph, fuel_flow_target, dt * 1.1)
        self.dynamics.vibration_mms = self._lag(self.dynamics.vibration_mms, vibration_target, dt * 1.0)
        self.dynamics.battery_voltage = self._lag(self.dynamics.battery_voltage, battery_target, dt * 0.6)

        return EngineTelemetry(
            rpm=self.dynamics.rpm,
            cht_c=self.dynamics.cht_c,
            egt_c=self.dynamics.egt_c,
            oil_pressure_kpa=self.dynamics.oil_pressure_kpa,
            oil_temperature_c=self.dynamics.oil_temperature_c,
            fuel_flow_lph=self.dynamics.fuel_flow_lph,
            vibration_mms=self.dynamics.vibration_mms,
            battery_voltage=self.dynamics.battery_voltage,
        )
