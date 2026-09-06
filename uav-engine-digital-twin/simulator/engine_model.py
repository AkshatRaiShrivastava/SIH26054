"""Reduced-order piston engine model for a UAV.

Calculates the 'True State' of the engine using physically sensible relationships
and first-order dynamics for continuity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .environment import EnvironmentModel, EnvironmentState
from .telemetry import EngineInputs, EngineState


@dataclass
class EngineDynamics:
    """Internal state of the engine's physical components."""
    rpm: float = 0.0
    cht_c: float = 20.0
    egt_c: float = 20.0
    oil_pressure_kpa: float = 0.0
    oil_temperature_c: float = 20.0
    fuel_flow_lph: float = 0.0
    vibration_mms: float = 0.0
    battery_voltage: float = 27.8


class EngineModel:
    """Synthetic engine model that computes physical truth.

    Inputs: Throttle, Load, Health, and Atmospheric conditions.
    Outputs: EngineState (Physical Truth).
    """

    def __init__(self) -> None:
        self.dynamics = EngineDynamics()
        self.environment = EnvironmentModel()

    @staticmethod
    def _lag(current: float, target: float, alpha: float) -> float:
        """First-order response filter."""
        return current + (target - current) * max(0.0, min(1.0, alpha))

    def step(self, inputs: EngineInputs, dt: float = 0.1, modifiers: Optional[Dict[str, float]] = None) -> EngineState:
        """Compute the next true state of the engine.

        Args:
            inputs: Current operational inputs (throttle, load, etc.).
            dt: Time step in seconds.
            modifiers: Physics modifiers from the FaultManager (e.g., efficiency).

        Returns:
            EngineState containing the current 'physical truth'.
        """
        mods = modifiers or {}
        fuel_eff = mods.get("fuel_efficiency", 1.0)
        cool_eff_mod = mods.get("cooling_efficiency", 1.0)
        oil_press_mod = mods.get("oil_pressure_base", 1.0)
        friction_mod = mods.get("internal_friction", 1.0)

        # 1. Get current environment state
        env_state = self.environment.get_state(
            inputs.altitude_m, inputs.ambient_temperature_c
        )

        # Density ratio vs sea level (approx 1.225 kg/m^3)
        rho_sea = 1.225
        density_ratio = env_state.air_density_kg_m3 / rho_sea

        # 2. Handle Engine Health and Age
        health = max(0.1, min(1.0, inputs.engine_health))
        age_penalty = min(0.2, inputs.engine_age_hours / 5000.0 * 0.2)
        effective_health = max(0.1, health - age_penalty)

        # 3. RPM Calculation
        # Base RPM + throttle-driven RPM, scaled by air density and health
        rpm_idle = 800.0
        rpm_max = 5800.0
        # RPM increases with throttle, but is also pushed by engine load (to maintain speed)
        rpm_target = rpm_idle + (rpm_max - rpm_idle) * (0.7 * inputs.throttle + 0.3 * inputs.engine_load) * density_ratio * (0.9 + 0.1 * effective_health)
        rpm_target = max(0.0, min(6200.0, rpm_target))

        # 4. Thermal Calculations (CHT/EGT)
        # Heat In: proportional to throttle and load
        # Heat Out: proportional to RPM (airflow) and density
        heat_in = (inputs.throttle * 80.0) + (inputs.engine_load * 50.0)
        cooling_eff = 0.03 * (self.dynamics.rpm / 1000.0) * density_ratio * effective_health * cool_eff_mod

        cht_target = 20.0 + heat_in - (cooling_eff * 120.0)
        cht_target = max(env_state.ambient_temperature_c, min(280.0, cht_target))

        egt_target = 150.0 + (inputs.throttle * 500.0) + (inputs.engine_load * 200.0)
        egt_target *= (1.0 + (1.0 - density_ratio) * 0.15) # Higher EGT at altitude
        egt_target = max(env_state.ambient_temperature_c, min(950.0, egt_target))

        # 5. Lubrication System
        # Oil pressure increases with RPM, decreases with temperature
        oil_pressure_target = 100.0 * oil_press_mod + (self.dynamics.rpm * 0.06) * effective_health
        oil_pressure_target -= max(0.0, self.dynamics.oil_temperature_c - 80.0) * 1.2
        oil_pressure_target = max(0.0, min(550.0, oil_pressure_target))

        # Oil temperature follows CHT with a slower lag
        oil_temp_target = env_state.ambient_temperature_c + (self.dynamics.cht_c - env_state.ambient_temperature_c) * 0.7
        oil_temp_target = max(env_state.ambient_temperature_c, min(150.0, oil_temp_target))

        # 6. Fuel Flow
        # Fuel flow based on RPM, throttle (richness), and density
        fuel_flow_target = (self.dynamics.rpm / 1000.0) * 4.0 * (1.0 + inputs.throttle * 0.5) * (1.0 / max(0.5, density_ratio))
        fuel_flow_target *= (1.0 + (1.0 - effective_health) * 0.15) # Less efficient engine burns more

        # 7. Vibration and Battery
        vibration_target = 0.2 + (self.dynamics.rpm / 5000.0) * 1.0 + (1.0 - effective_health) * 1.5
        battery_target = 28.0 - (0.5 if self.dynamics.rpm < 500 else 0.0)

        # 8. Apply First-Order Response (Lag)
        # Different time constants for different parameters
        self.dynamics.rpm = self._lag(self.dynamics.rpm, rpm_target, dt * 2.0)
        self.dynamics.cht_c = self._lag(self.dynamics.cht_c, cht_target, dt * 0.2)
        self.dynamics.egt_c = self._lag(self.dynamics.egt_c, egt_target, dt * 0.5)
        self.dynamics.oil_temperature_c = self._lag(self.dynamics.oil_temperature_c, oil_temp_target, dt * 0.1)
        self.dynamics.oil_pressure_kpa = self._lag(self.dynamics.oil_pressure_kpa, oil_pressure_target, dt * 1.5)
        self.dynamics.fuel_flow_lph = self._lag(self.dynamics.fuel_flow_lph, fuel_flow_target, dt * 1.0)
        self.dynamics.vibration_mms = self._lag(self.dynamics.vibration_mms, vibration_target, dt * 1.0)
        self.dynamics.battery_voltage = self._lag(self.dynamics.battery_voltage, battery_target, dt * 0.5)

        return EngineState(
            rpm=self.dynamics.rpm,
            cht_c=self.dynamics.cht_c,
            egt_c=self.dynamics.egt_c,
            oil_pressure_kpa=self.dynamics.oil_pressure_kpa,
            oil_temperature_c=self.dynamics.oil_temperature_c,
            fuel_flow_lph=self.dynamics.fuel_flow_lph,
            vibration_mms=self.dynamics.vibration_mms,
            battery_voltage=self.dynamics.battery_voltage,
        )
