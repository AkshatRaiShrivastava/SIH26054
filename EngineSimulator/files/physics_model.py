"""
physics_model.py
=================
Pure functions implementing the physics-informed "expected value" model.
Every function is stateless: expected_value = f(RPM, altitude, ambient_temp, ...)

This module has NO knowledge of missions, stages, faults, or time — it is
the reusable "what SHOULD this reading be, given these conditions" layer,
exactly as described in the physics-informed model spec:

    expected_value = f(RPM, altitude, ambient_temp, [oil_temp | AFR | throttle])
    deviation_pct  = (actual - expected) / expected * 100

All formulas and constants below are taken directly from the physics-informed
model document. Constants marked "starting estimate" are NOT DRDO-verified
values (no public dataset exists for the classified engine) -- they are
structurally-correct placeholders meant to be re-fit against a synthetic
healthy dataset, per the document's calibration methodology (section 2.9).
"""

import math

REDLINE_RPM = 5800
RHO0 = 1.225           # kg/m^3, sea-level reference density
STOICH_AFR = 14.7      # stoichiometric air/fuel ratio for gasoline
BSFC_G_PER_KWH = 285.0     # brake specific fuel consumption, from manual
FUEL_DENSITY_G_PER_L = 720.0

# Auto-calibrated against the manual's max-continuous-power reference point:
# ~58 kW at RPM=5500, throttle~0.95 (max continuous is slightly below WOT).
_REF_RPM = 5500.0
_REF_THROTTLE = 0.95
_REF_POWER_KW = 58.0
K_POWER = _REF_POWER_KW / (_REF_RPM * _REF_THROTTLE)   # kW per (rpm * throttle_fraction)

K_ALT_CHT = 15.0        # starting estimate, per doc section 2.3
# oil temp/pressure constants are taken as given in doc section 2.4


# ---------------------------------------------------------------------------
# 2.2 Foundation layer: standard atmosphere
# ---------------------------------------------------------------------------
def isa_temperature_c(altitude_m: float) -> float:
    """T(h) in Kelvin per ISA, returned in Celsius."""
    t_k = 288.15 - 0.0065 * altitude_m
    return t_k - 273.15


def density_ratio_sigma(altitude_m: float) -> float:
    """sigma = rho(h)/rho0, per the ISA power-law approximation."""
    return (1 - 2.2558e-5 * altitude_m) ** 4.2559


def ambient_temp_c(altitude_m: float, isa_dev_c: float) -> float:
    """Actual ambient temperature = ISA standard temp + weather deviation."""
    return isa_temperature_c(altitude_m) + isa_dev_c


# ---------------------------------------------------------------------------
# 2.3 Cylinder head temperature (CHT)
# ---------------------------------------------------------------------------
def cht_base_c(rpm: float) -> float:
    """
    Curve-fit placeholder anchored to the manual's stated band (~100-190 C).
    Re-fit this against your synthetic healthy dataset (doc section 2.9).
    """
    return 100.0 + 90.0 * (rpm / REDLINE_RPM)


def cht_expected_c(rpm: float, t_ambient_c: float, sigma: float) -> float:
    return cht_base_c(rpm) + 0.5 * (t_ambient_c - 15.0) - K_ALT_CHT * (sigma - 1.0)


# ---------------------------------------------------------------------------
# 2.4 Oil temperature and oil pressure (coupled pair)
# ---------------------------------------------------------------------------
def oil_temp_expected_c(rpm: float, t_ambient_c: float, sigma: float) -> float:
    return 55.0 + 0.009 * rpm + 0.6 * t_ambient_c - 8.0 * (sigma - 1.0)


def oil_pressure_expected_psi(rpm: float, oil_temp_c: float) -> float:
    """
    Two-piece curve: below 3500 RPM the manual specifies a 12 psi floor
    rather than a continuous formula (doc section 2.4) -- branch, don't
    interpolate, across that boundary.
    """
    if rpm < 3500:
        return 12.0
    viscosity_factor = math.exp(-0.02 * (oil_temp_c - 90.0))
    return 0.013 * rpm * viscosity_factor


# ---------------------------------------------------------------------------
# 2.5 Exhaust gas temperature (EGT)
# ---------------------------------------------------------------------------
def egt_expected_c(rpm: float, afr_actual: float) -> float:
    return 500.0 + 0.06 * rpm + 40.0 * (afr_actual - STOICH_AFR)


# ---------------------------------------------------------------------------
# 2.6 Fuel flow
# ---------------------------------------------------------------------------
def power_estimate_kw(rpm: float, throttle_fraction: float) -> float:
    return K_POWER * rpm * throttle_fraction


def fuel_flow_expected_lph(rpm: float, throttle_fraction: float) -> float:
    power_kw = power_estimate_kw(rpm, throttle_fraction)
    return (BSFC_G_PER_KWH * power_kw) / FUEL_DENSITY_G_PER_L


# ---------------------------------------------------------------------------
# 2.7 Vibration baseline (empirical, no closed-form physics -- doc section 2.7)
# ---------------------------------------------------------------------------
def vibration_baseline_g(rpm: float) -> float:
    """
    Smooth curve rising with RPM, with two resonance bumps representing
    propeller-harmonic bands. This stands in for "fit a curve against your
    synthetic healthy dataset" until real vibration data is available.
    """
    x = rpm / REDLINE_RPM
    base = 0.15 + 0.35 * x
    bump1 = 0.12 * math.exp(-((rpm - 3800) / 300.0) ** 2)
    bump2 = 0.08 * math.exp(-((rpm - 5200) / 250.0) ** 2)
    return base + bump1 + bump2


# ---------------------------------------------------------------------------
# Convenience: compute every expected value at once for a given state
# ---------------------------------------------------------------------------
def expected_state(rpm: float, altitude_m: float, isa_dev_c: float,
                    afr_nominal: float = 14.7, throttle_fraction: float = 0.5) -> dict:
    t_amb = ambient_temp_c(altitude_m, isa_dev_c)
    sigma = density_ratio_sigma(altitude_m)
    cht = cht_expected_c(rpm, t_amb, sigma)
    oil_temp = oil_temp_expected_c(rpm, t_amb, sigma)
    oil_pressure = oil_pressure_expected_psi(rpm, oil_temp)
    egt = egt_expected_c(rpm, afr_nominal)
    fuel_flow = fuel_flow_expected_lph(rpm, throttle_fraction)
    vibration = vibration_baseline_g(rpm)

    return {
        "rpm": rpm,
        "altitude_m": altitude_m,
        "ambient_temp_c": round(t_amb, 2),
        "sigma": round(sigma, 4),
        "cht_c": round(cht, 2),
        "oil_temp_c": round(oil_temp, 2),
        "oil_pressure_psi": round(oil_pressure, 2),
        "egt_c": round(egt, 2),
        "fuel_flow_lph": round(fuel_flow, 2),
        "vibration_g": round(vibration, 3),
    }


def deviation_pct(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0
    return (actual - expected) / expected * 100.0
