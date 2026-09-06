"""Environment model for altitude and temperature effects using ISA.

International Standard Atmosphere (ISA) approximation for the troposphere (up to 11km).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnvironmentState:
    """The current atmospheric conditions."""
    altitude_m: float
    ambient_temperature_c: float
    pressure_pa: float
    air_density_kg_m3: float


class EnvironmentModel:
    """Provides atmospheric parameters based on altitude.

    Reference: International Standard Atmosphere (ISA)
    """

    # Constants
    SEA_LEVEL_TEMP_K = 288.15  # 15 C
    SEA_LEVEL_PRESSURE_PA = 101325.0
    LAPSE_RATE = -0.0065       # K/m
    GAS_CONSTANT_AIR = 287.05  # J/(kg*K)
    GRAVITY = 9.80665          # m/s^2

    def get_state(self, altitude_m: float, surface_temp_c: float = 15.0) -> EnvironmentState:
        """Calculate atmospheric state for a given altitude.

        Args:
            altitude_m: Current altitude in meters.
            surface_temp_c: Temperature at sea level in Celsius.

        Returns:
            EnvironmentState containing T, P, and rho.
        """
        # Ensure altitude is non-negative
        alt = max(0.0, altitude_m)

        # Temperature at altitude (K)
        # T = T0 + L * h
        temp_k = (surface_temp_c + 273.15) + self.LAPSE_RATE * alt
        temp_c = temp_k - 273.15

        # Pressure at altitude (Pa)
        # P = P0 * (1 + L*h/T0)^(gM/RL)
        # For troposphere: P = P0 * (T/T0)^(5.25588)
        t0_k = (15.0 + 273.15) # Standard T0
        pressure_pa = self.SEA_LEVEL_PRESSURE_PA * (temp_k / t0_k)**5.25588

        # Air density (kg/m^3)
        # rho = P / (R * T)
        air_density = pressure_pa / (self.GAS_CONSTANT_AIR * temp_k)

        return EnvironmentState(
            altitude_m=alt,
            ambient_temperature_c=temp_c,
            pressure_pa=pressure_pa,
            air_density_kg_m3=air_density
        )

    def density_ratio(self, altitude_m: float, ambient_temperature_c: float) -> float:
        """Maintains compatibility with existing engine model for now.
        Returns ratio of density at altitude vs sea level.
        """
        state = self.get_state(altitude_m, ambient_temperature_c)
        rho_sea = self.SEA_LEVEL_PRESSURE_PA / (self.GAS_CONSTANT_AIR * self.SEA_LEVEL_TEMP_K)
        return state.air_density_kg_m3 / rho_sea

    def heat_load_factor(self, ambient_temperature_c: float, altitude_m: float) -> float:
        """Maintains compatibility with existing engine model for now.
        Simulates reduced cooling efficiency at high altitude/temp.
        """
        # Cooling efficiency decreases as air density decreases
        state = self.get_state(altitude_m, ambient_temperature_c)
        rho_sea = self.SEA_LEVEL_PRESSURE_PA / (self.GAS_CONSTANT_AIR * self.SEA_LEVEL_TEMP_K)
        density_ratio = state.air_density_kg_m3 / rho_sea

        # Factor > 1.0 means harder to cool (higher T)
        # Base factor + temperature penalty + density penalty
        return 1.0 + max(0.0, ambient_temperature_c - 20.0) * 0.01 + (1.0 - density_ratio) * 0.5
