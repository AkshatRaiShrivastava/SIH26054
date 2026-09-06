"""Prototype digital-twin constants for a MALE UAV piston engine demo.

These are stated engineering assumptions, not OEM-certified calibration values.
They are intentionally tunable in one place to support prototype calibration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicsConfig:
    T0_C: float = 15.0
    ATMOS_DENSITY_GRADIENT: float = 0.0065
    SIGMA_A: float = 2.2558e-5
    SIGMA_B: float = 4.2559
    CHT_BASE: float = 40.0
    CHT_RPM_GAIN: float = 0.018
    CHT_ALTITUDE_GAIN: float = 0.004
    OIL_TEMP_BASE: float = 68.0
    OIL_TEMP_RPM_GAIN: float = 0.004
    OIL_TEMP_LOAD_GAIN: float = 0.12
    OIL_PRESSURE_BASE: float = 220.0
    OIL_PRESSURE_RPM_PEAK: float = 3500.0
    OIL_PRESSURE_RPM_GAIN: float = 0.035
    OIL_PRESSURE_LOAD_GAIN: float = 0.8
    EGT_BASE: float = 430.0
    EGT_AFR_GAIN: float = 34.0
    EGT_RPM_GAIN: float = 0.062
    FUEL_FLOW_BASE: float = 6.5
    FUEL_FLOW_LOAD_GAIN: float = 0.08
    FUEL_FLOW_RPM_GAIN: float = 0.0014
    VIBRATION_BASELINE: float = 1.0
    VIBRATION_RPM_GAIN: float = 0.00022
    HEALTH_PENALTY_WEIGHT: float = 0.6
    ANOMALY_WEIGHT: float = 40.0
    MAX_HEALTH_INDEX: float = 100.0


PHYSICS_CONFIG = PhysicsConfig()
