# Configuration Guide — Digital Twin Pipeline

This guide explains how to customize the pipeline for different scenarios.

## Quick Reference: Adjustable Parameters

All parameters are defined in `config.py`. Edit this file before running flights to customize behavior.

---

## 1. Engine Configuration

### Change Engine Model

**Location:** `config.py` → `ENGINE_CONFIG`

**Current (Rotax 914 Turbocharged):**
```python
ENGINE_CONFIG = {
    "model": "Rotax 914",
    "type": "turbocharged",
    "displacement_cc": 1200,
    "nominal_power_hp": 115,
}
```

**To use naturally-aspirated (e.g., Rotax 912):**
```python
ENGINE_CONFIG = {
    "model": "Rotax 912",
    "type": "naturally_aspirated",
    "displacement_cc": 1200,
    "nominal_power_hp": 97,
}
```

**Effect:** Physics layer will apply power-loss corrections differently.

### Expected Values at Cruise

**Location:** `config.py` → `EXPECTED_VALUES_NOMINAL`

Adjust baseline expectations:
```python
EXPECTED_VALUES_NOMINAL = {
    "rpm": 3200,              # increase for higher-cruise configs
    "cht_c": 150,             # cylinder head temp baseline
    "egt_c": 700,             # exhaust gas temp baseline
    "oil_temp_c": 90,         # oil temperature baseline
    "oil_pressure_psi": 45,   # oil pressure baseline
    ...
}
```

**Effect:** All deviations will be computed relative to these nominal values.

### Sensor Noise Levels

**Location:** `config.py` → `SENSOR_NOISE`

Adjust how much noise each sensor has:
```python
SENSOR_NOISE = {
    "rpm": 50,              # ±50 RPM std dev
    "cht_c": 2.5,           # ±2.5°C std dev
    "oil_pressure_psi": 1.0,  # ±1 psi std dev
    ...
}
```

**Effect:** Higher noise = more fluctuation, more debouncing needed.

---

## 2. Mission Profile

### Change Flight Phases

**Location:** `config.py` → `MISSION_PHASES`

Default:
```python
MISSION_PHASES = {
    "preflight": {"start_s": 0, "duration_s": 600, "rpm_target": 1000},
    "takeoff": {"start_s": 600, "duration_s": 180, "rpm_target": 5500},
    "climb": {"start_s": 780, "duration_s": 900, "rpm_target": 4500},
    "cruise": {"start_s": 1680, "duration_s": 2400, "rpm_target": 3200},
    "descent": {"start_s": 4080, "duration_s": 600, "rpm_target": 2500},
    "landing": {"start_s": 4680, "duration_s": 300, "rpm_target": 1500},
}

TOTAL_FLIGHT_DURATION_S = 5000  # ~1.4 hours
```

**Example: Extended Cruise**
```python
MISSION_PHASES = {
    ...
    "cruise": {"start_s": 1680, "duration_s": 5400, "rpm_target": 3200},  # 90 min cruise
    ...
}
TOTAL_FLIGHT_DURATION_S = 8000  # ~2.2 hours
```

**Effect:** Longer phases = more data points, faults develop over longer durations.

---

## 3. Climate Zones & Environment

### Add a New Climate Zone

**Location:** `config.py` → `CLIMATE_ZONES`

**Example: High-Altitude Mountain Region**
```python
"mountain_high_alt": {
    "name": "High Altitude Mountain",
    "altitude_m": 5000,            # 5000m baseline
    "temp_c_baseline": -5,         # very cold
    "humidity_pct_baseline": 30,   # dry
    "dust_accumulation_rate": 0.05,  # low dust in mountains
    "maritime_exposure": False,
},
```

Then use: `python generate_telemetry.py --flight-id FL-MOUNTAIN-001 --zone mountain_high_alt`

### Adjust Icing Risk Thresholds

**Location:** `config.py` → `ICING_RISK`

**Current (Conservative):**
```python
ICING_RISK = {
    "high": {
        "temp_min_c": 0,
        "temp_max_c": 15,        # icing risk up to 15°C
        "humidity_min_pct": 50,
    },
    "moderate": {...}
}
```

**More conservative (extended icing envelope):**
```python
ICING_RISK = {
    "high": {
        "temp_min_c": -2,        # extend to -2°C
        "temp_max_c": 18,        # extend to 18°C
        "humidity_min_pct": 45,  # lower humidity threshold
    },
    ...
}
```

**Effect:** More flights will receive HIGH icing advisory in applicable zones.

---

## 4. Fault Profiles

### Add a Custom Fault

**Location:** `config.py` → `FAULT_PROFILES`

**Example: Alternator Failure**
```python
FAULT_PROFILES = {
    ...
    "alternator_failure": {
        "parameter": "battery_v",
        "severity_per_s": -0.05,  # voltage drops 0.05V/s
        "min_value": 10,          # stop at 10V
        "typical_start_s": 3600,  # occurs after 1 hour
    },
}
```

### Adjust Fault Severity

**Low severity (slow degradation):**
```python
"oil_pressure_drop": {
    "severity_per_s": -0.1,  # slow drop
}
```

**High severity (rapid failure):**
```python
"oil_pressure_drop": {
    "severity_per_s": -0.5,  # fast drop
}
```

**Effect:** Faults with different severity rates will appear on the dashboard with different urgency.

---

## 5. Debouncing Behavior

### Change Debounce Sensitivity

**Location:** `config.py` → `DEBOUNCE_CONFIG`

**Current (aggressive debouncing - prevents flicker):**
```python
DEBOUNCE_CONFIG = {
    "window_packets": 5,         # look at 5 packets
    "threshold_packets": 3,      # need 3 to agree (60% consensus)
    "status_thresholds": {
        "normal_to_caution": 5.0,      # 5% deviation
        "caution_to_critical": 15.0,   # 15% deviation
    },
}
```

**Conservative (fast response, more flicker possible):**
```python
DEBOUNCE_CONFIG = {
    "window_packets": 3,         # smaller window
    "threshold_packets": 2,      # lower threshold (67% consensus)
    "status_thresholds": {
        "normal_to_caution": 3.0,      # tighter threshold
        "caution_to_critical": 10.0,
    },
}
```

**Effect:** 
- Larger window/higher threshold = delayed response but less flicker
- Smaller window/lower threshold = faster response but more sensitivity to noise

---

## 6. Subsystem Health Calculation

### Adjust Subsystem Weights

**Location:** `config.py` → `SUBSYSTEM_WEIGHTS`

**Current (equal importance):**
```python
SUBSYSTEM_WEIGHTS = {
    "combustion": 0.35,
    "lubrication": 0.30,
    "fuel_system": 0.20,
    "mechanical": 0.15,
}
```

**Prioritize lubrication (critical for engine life):**
```python
SUBSYSTEM_WEIGHTS = {
    "combustion": 0.25,
    "lubrication": 0.50,      # 50% of health score
    "fuel_system": 0.15,
    "mechanical": 0.10,
}
```

**Effect:** Health score will drop faster if lubrication issues are detected.

### Change Parameter Assignments to Subsystems

**Location:** `config.py` → `SUBSYSTEM_PARAMETERS`

**Current:**
```python
SUBSYSTEM_PARAMETERS = {
    "combustion": ["egt_c", "cht_c", "afr"],
    "lubrication": ["oil_temp_c", "oil_pressure_psi"],
    "fuel_system": ["fuel_flow_lph"],
    "mechanical": ["vibration_g", "battery_v"],
}
```

**Example: Move battery to own subsystem**
```python
SUBSYSTEM_PARAMETERS = {
    "combustion": ["egt_c", "cht_c", "afr"],
    "lubrication": ["oil_temp_c", "oil_pressure_psi"],
    "fuel_system": ["fuel_flow_lph"],
    "mechanical": ["vibration_g"],
    "electrical": ["battery_v"],
}
```

**Note:** Must also update `SUBSYSTEM_WEIGHTS` to include the new subsystem.

---

## 7. Environmental Effects

### Dust/Filter Degradation

**Location:** `config.py` → `DUST_FILTER_PARAMS`

**Current (unfitted placeholders):**
```python
DUST_FILTER_PARAMS = {
    "k_dust": 0.001,              # filter accumulation coefficient
    "fuel_flow_sensitivity": 0.002,  # 0.2% reduction per 1% clogging
}
```

**Increase dust effect (hotter climates):**
```python
DUST_FILTER_PARAMS = {
    "k_dust": 0.002,              # double the accumulation
    "fuel_flow_sensitivity": 0.005,  # 0.5% reduction per 1% clogging
}
```

**Effect:** Desert flights will show faster fuel flow degradation over time.

### Corrosion Rate

**Location:** `config.py` → `CORROSION_PARAMS`

**Current:**
```python
CORROSION_PARAMS = {
    "rate_per_hour": 0.01,              # 0.01 index points/hour in maritime
    "maintenance_threshold": 50,        # advisory at index=50
}
```

**Faster corrosion (more aggressive environment):**
```python
CORROSION_PARAMS = {
    "rate_per_hour": 0.05,              # 5x faster
    "maintenance_threshold": 30,        # lower threshold
}
```

**Effect:** Maritime flights will accumulate corrosion faster and trigger maintenance warnings sooner.

---

## 8. Packet Generation Timing

### Change Packet Interval

**Location:** `config.py` → `PACKET_INTERVAL_S`

**Current (realistic telemetry rate):**
```python
PACKET_INTERVAL_S = 2.5         # one packet every 2.5 seconds
PACKET_INTERVAL_JITTER_S = 0.5  # ±0.5 second randomness
```

**Faster sampling (high-frequency diagnostics):**
```python
PACKET_INTERVAL_S = 0.5         # 10 Hz
PACKET_INTERVAL_JITTER_S = 0.1  # ±0.1 second
```

**Slower sampling (low-bandwidth link):**
```python
PACKET_INTERVAL_S = 5.0         # one every 5 seconds
PACKET_INTERVAL_JITTER_S = 0.2
```

**Effect:** Faster = more data points, debouncing may need adjustment.

---

## Common Scenarios

### Scenario 1: Arctic High-Altitude Mission

```python
# In config.py

MISSION_PHASES = {
    ...
    "climb": {"start_s": 780, "duration_s": 1800, "rpm_target": 4000},  # long climb
    "cruise": {"start_s": 2580, "duration_s": 3600, "rpm_target": 3500},  # high cruise
    ...
}

CLIMATE_ZONES["arctic"] = {
    "name": "Arctic High Altitude",
    "altitude_m": 6000,
    "temp_c_baseline": -20,
    "humidity_pct_baseline": 25,
    "dust_accumulation_rate": 0.0,
    "maritime_exposure": False,
}

ICING_RISK = {
    "high": {
        "temp_min_c": -15,
        "temp_max_c": 10,
        "humidity_min_pct": 30,  # lower threshold at altitude
    },
}
```

**Run:**
```bash
python generate_telemetry.py --flight-id FL-ARCTIC-001 --zone arctic --fault-chance 0.2
```

### Scenario 2: Monsoon Maritime Surveillance

```python
# In config.py

MISSION_PHASES = {
    ...
    "cruise": {"start_s": 1680, "duration_s": 7200, "rpm_target": 3200},  # very long
    ...
}
TOTAL_FLIGHT_DURATION_S = 9600  # 2.6 hours

CORROSION_PARAMS = {
    "rate_per_hour": 0.10,  # aggressive saltwater corrosion
    "maintenance_threshold": 20,  # alert sooner
}
```

**Run:**
```bash
python generate_telemetry.py --flight-id FL-MONSOON-001 --zone monsoon_belt --fault-chance 0.3
```

### Scenario 3: High-Reliability Testing

```python
# In config.py

SENSOR_NOISE = {
    param: noise * 0.3 for param, noise in SENSOR_NOISE.items()
}  # 70% reduction in noise

DEBOUNCE_CONFIG = {
    "window_packets": 10,
    "threshold_packets": 8,  # very strict consensus
    "status_thresholds": {
        "normal_to_caution": 8.0,
        "caution_to_critical": 20.0,
    },
}
```

**Run:**
```bash
python generate_telemetry.py --flight-id FL-RELIABLE-001 --zone ior_maritime --fault-chance 0.0
```

---

## Validation After Changes

After editing `config.py`, validate your changes:

```bash
# Check for syntax errors
python -c "import config; print('✓ Config loaded')"

# Run a short validation flight
python generate_telemetry.py --flight-id FL-TEST-CONFIG-001 --zone ior_maritime --fault-chance 0.1

# Check telemetry was generated
sqlite3 digital_twin.db "SELECT COUNT(*) FROM telemetry WHERE flight_id='FL-TEST-CONFIG-001'"

# Evaluate it
python physics_layer.py --flight-id FL-TEST-CONFIG-001 --replay

# View in dashboard
streamlit run dashboard.py
```

---

## Tips for Different Use Cases

| Use Case | Adjust | Rationale |
|----------|--------|-----------|
| **Fast diagnosis** | Debounce window smaller, thresholds tighter | Detect issues quickly |
| **Realistic simulation** | Use actual sensor noise specs | Match real aircraft |
| **Stress testing** | Increase fault chance, shorten intervals | Find failure modes |
| **Icing study** | Add icing envelope, lower humidity threshold | Focus on icing risk |
| **Maintenance tracking** | Increase corrosion rate, dust sensitivity | Emphasize maintenance |
| **Proof of concept** | No faults, low noise, lenient debounce | Clean, stable demo |

---

## Questions?

- See `plan.md` for the full implementation plan
- See `README.md` for usage instructions
- Check inline comments in each module for detailed explanations

**Happy tuning! ✈️**
