"""
Configuration and parameters for the Digital Twin Pipeline.
Baseline: Rotax 912/914 turbocharged engine profile.
"""

# ============================================================================
# MISSION PROFILE - Timeline and phases
# ============================================================================

MISSION_PHASES = {
    "preflight": {"start_s": 0, "duration_s": 600, "rpm_target": 1000},
    "takeoff": {"start_s": 600, "duration_s": 180, "rpm_target": 5500},
    "climb": {"start_s": 780, "duration_s": 900, "rpm_target": 4500},
    "cruise": {"start_s": 1680, "duration_s": 2400, "rpm_target": 3200},
    "descent": {"start_s": 4080, "duration_s": 600, "rpm_target": 2500},
    "landing": {"start_s": 4680, "duration_s": 300, "rpm_target": 1500},
}

TOTAL_FLIGHT_DURATION_S = 5000  # ~1.4 hours

# ============================================================================
# ENGINE PARAMETERS - Rotax 912/914 (turbocharged)
# ============================================================================

ENGINE_CONFIG = {
    "model": "Rotax 914",
    "type": "turbocharged",
    "displacement_cc": 1200,
    "nominal_power_hp": 115,  # turbocharged at altitude
}

# Expected values for each parameter (nominal cruise, sea level)
EXPECTED_VALUES_NOMINAL = {
    "rpm": 3200,
    "cht_c": 150,
    "egt_c": 700,
    "oil_temp_c": 90,
    "oil_pressure_psi": 45,
    "fuel_flow_lph": 32,
    "vibration_g": 0.5,
    "battery_v": 14.0,
    "afr": 13.2,
}

# Sensor noise levels (one-sigma Gaussian noise, applied via OU process)
SENSOR_NOISE = {
    "rpm": 50,
    "cht_c": 2.5,
    "egt_c": 15,
    "oil_temp_c": 1.5,
    "oil_pressure_psi": 1.0,
    "fuel_flow_lph": 0.8,
    "vibration_g": 0.02,
    "battery_v": 0.1,
    "afr": 0.1,
}

# OU Process parameters (mean reversion)
OU_THETA = {
    "rpm": 0.1,
    "cht_c": 0.05,
    "egt_c": 0.08,
    "oil_temp_c": 0.06,
    "oil_pressure_psi": 0.05,
    "fuel_flow_lph": 0.1,
    "vibration_g": 0.15,
    "battery_v": 0.05,
    "afr": 0.08,
}

# ============================================================================
# FAULT INJECTION PARAMETERS
# ============================================================================

FAULT_PROFILES = {
    "oil_pressure_drop": {
        "parameter": "oil_pressure_psi",
        "severity_per_s": -0.2,  # psi/s degradation
        "min_value": 15,  # floor
        "typical_start_s": 2400,  # appears at cruise, ~40 min into flight
    },
    "cht_rise": {
        "parameter": "cht_c",
        "severity_per_s": 0.5,  # °C/s rise
        "max_value": 250,  # floor
        "typical_start_s": 3000,
    },
    "fuel_flow_drop": {
        "parameter": "fuel_flow_lph",
        "severity_per_s": -0.05,  # L/h/s degradation
        "min_value": 10,
        "typical_start_s": 1800,
    },
}

# ============================================================================
# ENVIRONMENTAL PARAMETERS - Climate zones and profiles
# ============================================================================

CLIMATE_ZONES = {
    "himalayan": {
        "name": "Himalayan High Altitude",
        "altitude_m": 3000,
        "temp_c_baseline": 5,
        "humidity_pct_baseline": 40,
        "dust_accumulation_rate": 0.1,  # filter-hours / flight-hour
        "maritime_exposure": False,
    },
    "desert": {
        "name": "Desert",
        "altitude_m": 500,
        "temp_c_baseline": 35,
        "humidity_pct_baseline": 15,
        "dust_accumulation_rate": 0.8,  # very high dust load
        "maritime_exposure": False,
    },
    "ior_maritime": {
        "name": "Indian Ocean Region Maritime",
        "altitude_m": 100,
        "temp_c_baseline": 28,
        "humidity_pct_baseline": 75,
        "dust_accumulation_rate": 0.2,
        "maritime_exposure": True,
    },
    "monsoon_belt": {
        "name": "Monsoon Belt",
        "altitude_m": 200,
        "temp_c_baseline": 26,
        "humidity_pct_baseline": 80,
        "dust_accumulation_rate": 0.3,
        "maritime_exposure": False,
    },
}

# ============================================================================
# ICING RISK THRESHOLDS (Climate Doc §3.2)
# ============================================================================

ICING_RISK = {
    "high": {
        "temp_min_c": 0,
        "temp_max_c": 15,  # updated from 38 based on practical icing envelope
        "humidity_min_pct": 50,
    },
    "moderate": {
        "temp_min_c": 0,
        "temp_max_c": 15,
        "humidity_min_pct": 30,
    },
}

# ============================================================================
# DUST/FILTER LOADING (Climate Doc §3.3)
# ============================================================================

DUST_FILTER_PARAMS = {
    "k_dust": 0.001,  # unfitted placeholder - filter accumulation coefficient
    "fuel_flow_sensitivity": 0.002,  # 0.2% fuel flow reduction per 1% filter clogging
}

# ============================================================================
# MARITIME CORROSION (Climate Doc §3.4)
# ============================================================================

CORROSION_PARAMS = {
    "rate_per_hour": 0.01,  # corrosion index points per maritime hour
    "maintenance_threshold": 50,  # advisory triggers at this level
}

# ============================================================================
# TELEMETRY PACKET PARAMETERS
# ============================================================================

PACKET_INTERVAL_S = 2.5  # telemetry packet interval (nominal)
PACKET_INTERVAL_JITTER_S = 0.5  # random jitter ±

# ============================================================================
# DEBOUNCE PARAMETERS (§2.3 - Flicker fix)
# ============================================================================

DEBOUNCE_CONFIG = {
    "window_packets": 5,  # rolling window size
    "threshold_packets": 3,  # require 3 of 5 packets to agree on new status
    "status_thresholds": {
        "normal_to_caution": 5.0,  # deviation % threshold
        "caution_to_critical": 15.0,
    },
}

# ============================================================================
# AIRFRAME IDENTITY (Cross-flight tracking)
# ============================================================================

DEFAULT_AIRFRAME_ID = "AIRFRAME-SIH26054-001"  # Simulated tail number

# ============================================================================
# SUBSYSTEM HEALTH CALCULATIONS
# ============================================================================

SUBSYSTEM_PARAMETERS = {
    "combustion": ["egt_c", "cht_c", "afr"],
    "lubrication": ["oil_temp_c", "oil_pressure_psi"],
    "fuel_system": ["fuel_flow_lph"],
    "mechanical": ["vibration_g", "battery_v"],
}

# Weighting for subsystem health rollup
SUBSYSTEM_WEIGHTS = {
    "combustion": 0.35,
    "lubrication": 0.30,
    "fuel_system": 0.20,
    "mechanical": 0.15,
}

# ============================================================================
# ALTITUDE EFFECTS (Density Altitude - Climate Doc §3.1)
# ============================================================================

POWER_LOSS_CORRECTION = {
    "naturally_aspirated": 3.0,  # hp/1000 ft for O-320 and similar
    "turbocharged": 0.0,  # Rotax 914 turbo compensates up to rated altitude
}

# Rated altitude for turbocharged engine (turbo boost limit)
TURBOCHARGED_RATED_ALT_FT = 10000

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_PATH = os.path.join(BASE_DIR, "data", "digital_twin.db")
DEBUG_DATABASE_PATH = os.path.join(BASE_DIR, "data", "debug_eval_state.db")

if __name__ == "__main__":
    print("Configuration loaded. Engine baseline: Rotax 914 (turbocharged)")
    print(f"Total flight duration: {TOTAL_FLIGHT_DURATION_S / 60:.1f} minutes")
