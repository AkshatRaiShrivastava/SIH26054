from __future__ import annotations

from physics.atmosphere import ambient_temperature_c, density_ratio
from physics.config import PHYSICS_CONFIG


def expected_cht_c(rpm: float, altitude_m: float, ambient_temp_c: float, oil_temp_c: float = 90.0) -> float:
    sigma = density_ratio(altitude_m)
    temp = PHYSICS_CONFIG.CHT_BASE + rpm * PHYSICS_CONFIG.CHT_RPM_GAIN + altitude_m * PHYSICS_CONFIG.CHT_ALTITUDE_GAIN * (1.0 / max(sigma, 0.1))
    temp += max(0.0, oil_temp_c - ambient_temp_c) * 0.18
    return temp


def expected_egt_c(rpm: float, ambient_temp_c: float, afr: float = 14.7) -> float:
    afr_factor = max(0.0, (afr - 14.7) * 35.0)
    return PHYSICS_CONFIG.EGT_BASE + rpm * PHYSICS_CONFIG.EGT_RPM_GAIN + (ambient_temp_c * 1.5) + afr_factor


def expected_oil_temperature_c(rpm: float, oil_temp_actual: float, ambient_temp_c: float, load_pct: float = 50.0) -> float:
    return max(50.0, oil_temp_actual * 0.95 + (ambient_temp_c * 0.15) + (rpm * 0.0024) + load_pct * 0.15)


def expected_oil_pressure_kpa(rpm: float, load_pct: float = 50.0) -> float:
    base = PHYSICS_CONFIG.OIL_PRESSURE_BASE + (rpm / 1000.0) * 25.0
    if rpm < PHYSICS_CONFIG.OIL_PRESSURE_RPM_PEAK:
        base += (PHYSICS_CONFIG.OIL_PRESSURE_RPM_PEAK - rpm) * 0.03
    else:
        base -= (rpm - PHYSICS_CONFIG.OIL_PRESSURE_RPM_PEAK) * 0.025
    base += load_pct * PHYSICS_CONFIG.OIL_PRESSURE_LOAD_GAIN
    return max(140.0, min(500.0, base))


def expected_fuel_flow_lph(rpm: float, load_pct: float = 50.0) -> float:
    return PHYSICS_CONFIG.FUEL_FLOW_BASE + rpm * PHYSICS_CONFIG.FUEL_FLOW_RPM_GAIN + load_pct * PHYSICS_CONFIG.FUEL_FLOW_LOAD_GAIN


def expected_vibration_baseline(rpm: float) -> float:
    return PHYSICS_CONFIG.VIBRATION_BASELINE + rpm * PHYSICS_CONFIG.VIBRATION_RPM_GAIN
