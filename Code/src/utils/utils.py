"""
Utilities for the Digital Twin Pipeline.
Includes OU process, noise generation, and helper functions.
"""

import random
from dataclasses import dataclass
from typing import Dict
import hashlib


@dataclass
class OUProcess:
    """
    Ornstein-Uhlenbeck process for smooth noise generation.
    
    Model: dx = θ(μ - x) dt + σ dW
    - θ: mean reversion rate
    - μ: long-term mean
    - σ: volatility (noise amplitude)
    - x: current state
    """

    mean: float
    theta: float
    sigma: float
    x: float = None

    def __post_init__(self):
        if self.x is None:
            self.x = self.mean

    def step(self, dt: float = 1.0, rng: random.Random = None) -> float:
        """
        Advance the OU process by dt seconds.
        
        Args:
            dt: time step
            rng: random.Random instance for reproducibility
        
        Returns:
            New state value
        """
        if rng is None:
            rng = random.Random()

        # Gaussian increment
        dW = rng.gauss(0, 1) * (dt ** 0.5)

        # OU update: x_new = x + θ(μ - x)dt + σ dW
        self.x += self.theta * (self.mean - self.x) * dt + self.sigma * dW
        return self.x


def seed_from_flight_id(flight_id: str) -> int:
    """
    Deterministic seed generation from flight_id string.
    Same flight_id always produces the same seed, ensuring reproducibility.
    
    Args:
        flight_id: string identifier for the flight
    
    Returns:
        integer seed for random.Random()
    """
    # Hash the flight_id to get a deterministic integer
    hash_obj = hashlib.md5(flight_id.encode("utf-8"))
    seed = int(hash_obj.hexdigest(), 16) & 0x7FFFFFFF  # 31-bit positive int
    return seed


def get_phase_at_time(mission_time_s: float, mission_phases: Dict) -> str:
    """
    Determine which mission phase is active at a given mission time.
    
    Args:
        mission_time_s: elapsed time in mission (seconds)
        mission_phases: dict of phase definitions with 'start_s' and 'duration_s'
    
    Returns:
        phase name string
    """
    for phase_name, phase_def in mission_phases.items():
        start = phase_def["start_s"]
        end = start + phase_def["duration_s"]
        if start <= mission_time_s < end:
            return phase_name
    return "post_flight"  # flight ended


def compute_density_altitude(
    altitude_m: float, ambient_temp_c: float, pressure_altitude_m: float = None
) -> float:
    """
    Compute density altitude from geometric altitude and temperature.
    Formula from Climate Doc §3.1:
    DA = PA + 120 × (OAT − (15 − 1.98 × PA/1000))
    
    Args:
        altitude_m: geometric altitude (m)
        ambient_temp_c: outside air temperature (°C)
        pressure_altitude_m: pressure altitude (m), defaults to geometric if None
    
    Returns:
        density altitude in meters
    """
    if pressure_altitude_m is None:
        pressure_altitude_m = altitude_m

    # Formula in meters (not feet)
    oat = ambient_temp_c
    pa_km = pressure_altitude_m / 1000.0

    da_m = pressure_altitude_m + 120 * (oat - (15 - 1.98 * pa_km))
    return da_m


def classify_icing_risk(
    ambient_temp_c: float,
    humidity_pct: float,
    high_threshold_temp_min: float = 0,
    high_threshold_temp_max: float = 15,
    high_threshold_humidity: float = 50,
    moderate_threshold_humidity: float = 30,
) -> str:
    """
    Classify icing risk based on temperature and humidity.
    From Climate Doc §3.2.
    
    Args:
        ambient_temp_c: outside air temperature (°C)
        humidity_pct: relative humidity (%)
        high_threshold_temp_min: low temp bound for high icing risk (°C)
        high_threshold_temp_max: high temp bound for high icing risk (°C)
        high_threshold_humidity: RH threshold for high icing risk (%)
        moderate_threshold_humidity: RH threshold for moderate icing risk (%)
    
    Returns:
        "HIGH", "MODERATE", or "LOW"
    """
    in_icing_envelope = (
        high_threshold_temp_min <= ambient_temp_c <= high_threshold_temp_max
    )

    if not in_icing_envelope:
        return "LOW"

    if humidity_pct >= high_threshold_humidity:
        return "HIGH"
    elif humidity_pct >= moderate_threshold_humidity:
        return "MODERATE"
    else:
        return "LOW"


def apply_filter_degradation(
    base_fuel_flow_lph: float,
    hours_since_filter_service: float,
    climate_zone: str,
    dust_factor: float = 0.001,
    fuel_flow_sensitivity: float = 0.002,
) -> float:
    """
    Apply dust/filter-loading drift to expected fuel flow.
    From Climate Doc §3.3.
    
    Args:
        base_fuel_flow_lph: nominal fuel flow (L/h)
        hours_since_filter_service: cumulative hours since last service
        climate_zone: climate zone name (affects dust accumulation)
        dust_factor: base dust accumulation coefficient (unfitted placeholder)
        fuel_flow_sensitivity: fuel flow reduction per unit filter clogging
    
    Returns:
        adjusted fuel flow (L/h)
    """
    # Zone-dependent dust exposure
    zone_factors = {
        "himalayan": 0.1,
        "desert": 0.8,
        "ior_maritime": 0.2,
        "monsoon_belt": 0.3,
    }
    zone_factor = zone_factors.get(climate_zone, 0.2)

    dust_exposure = hours_since_filter_service * zone_factor * dust_factor
    filter_health_pct = max(0, 100 - 100 * dust_exposure)

    # Fuel flow reduction
    adjustment = fuel_flow_sensitivity * (100 - filter_health_pct)
    adjusted_ff = base_fuel_flow_lph * (1 - adjustment)

    return adjusted_ff


def debounce_status(
    status_history: list, new_status: str, threshold_count: int = 3
) -> tuple:
    """
    Debounce status changes using a rolling window.
    
    Args:
        status_history: list of recent status values (most recent first)
        new_status: candidate new status
        threshold_count: how many consecutive packets required to confirm change
    
    Returns:
        tuple (debounced_status, updated_history)
    """
    # Keep last N statuses
    history = [new_status] + status_history[:4]

    # Check if new status is dominant in window
    count_new = sum(1 for s in history if s == new_status)

    if count_new >= threshold_count:
        confirmed_status = new_status
    else:
        # Keep previous status if new one isn't dominant yet
        confirmed_status = history[1] if len(history) > 1 else new_status

    return confirmed_status, history


if __name__ == "__main__":
    # Test reproducibility
    seed1 = seed_from_flight_id("FL-2026-08-30-001")
    seed2 = seed_from_flight_id("FL-2026-08-30-001")
    assert seed1 == seed2, "Seeds should be identical for same flight_id"
    print(f"Reproducibility test passed: seed={seed1}")

    # Test OU process reproducibility
    rng1 = random.Random(seed1)
    ou1 = OUProcess(mean=100, theta=0.1, sigma=5)
    values1 = [ou1.step(rng=rng1) for _ in range(10)]

    rng2 = random.Random(seed1)
    ou2 = OUProcess(mean=100, theta=0.1, sigma=5)
    values2 = [ou2.step(rng=rng2) for _ in range(10)]

    assert values1 == values2, "OU process should be reproducible"
    print(f"OU process reproducibility test passed")

    # Test icing risk
    risk = classify_icing_risk(5, 60)
    assert risk == "HIGH", "5°C + 60% RH should be HIGH icing risk"
    print(f"Icing risk classification test passed: {risk}")
