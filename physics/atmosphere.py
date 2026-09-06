"""Atmosphere model used by the digital twin.

Prototype design assumption: the density ratio and ambient temperature formulas are
simple engineering approximations for a MALE UAV piston-engine demonstrator.
"""

from __future__ import annotations

from math import pow

from physics.config import PHYSICS_CONFIG


def ambient_temperature_c(altitude_m: float, t0_c: float = PHYSICS_CONFIG.T0_C) -> float:
    return t0_c - PHYSICS_CONFIG.ATMOS_DENSITY_GRADIENT * altitude_m


def density_ratio(altitude_m: float) -> float:
    sigma = (1.0 - PHYSICS_CONFIG.SIGMA_A * altitude_m) ** PHYSICS_CONFIG.SIGMA_B
    return max(0.15, sigma)
