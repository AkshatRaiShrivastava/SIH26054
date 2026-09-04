"""Environment model for altitude and temperature effects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EnvironmentState:
    altitude_m: float
    ambient_temperature_c: float


class EnvironmentModel:
    """Small environment model that estimates density and thermal effects."""

    @staticmethod
    def density_ratio(altitude_m: float, ambient_temperature_c: float) -> float:
        # Simple ISA-inspired approximation. Good enough for a prototype.
        altitude_factor = max(0.35, 1.0 - altitude_m / 22000.0)
        temp_factor = max(0.85, 1.0 - max(0.0, ambient_temperature_c - 15.0) / 160.0)
        return max(0.3, altitude_factor * temp_factor)

    @staticmethod
    def heat_load_factor(ambient_temperature_c: float, altitude_m: float) -> float:
        return 1.0 + max(0.0, ambient_temperature_c - 20.0) * 0.012 + altitude_m / 60000.0
