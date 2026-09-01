# Digital Twin Pipeline — UAV Engine & Environmental Monitoring

A comprehensive simulation and monitoring system for UAV (Unmanned Aerial Vehicle) telemetry, engine diagnostics, and environmental awareness. Built on Python with SQLite, featuring reproducible flight simulation, physics-based condition monitoring, and an interactive Streamlit dashboard.

**Key Features:**
- ✅ **Reproducible Telemetry Generation** — same flight ID always produces identical data
- ✅ **Seeded Randomness** — smooth noise via Ornstein-Uhlenbeck processes, consistent fault injection
- ✅ **Physics-Based Evaluation** — expected values, deviation detection, debounced status (no flicker)
- ✅ **Environmental Awareness** — icing risk, density altitude, filter degradation, corrosion tracking
- ✅ **Live & Historical Views** — monitor active flights or replay archived missions
- ✅ **Subsystem Health Tracking** — combustion, lubrication, fuel, mechanical health scores
- ✅ **Fault Attribution** — icing-aware fault categorization

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python database.py
```

This creates an empty SQLite database (`digital_twin.db`) with all required tables.

### 3. Generate a Flight

```bash
python generate_telemetry.py --flight-id FL-2026-08-30-001 \
    --zone ior_maritime \
    --fault-chance 0.4
```

**Options:**
- `--flight-id`: Unique identifier (e.g., `FL-2026-08-30-001`)
- `--zone`: Climate zone: `himalayan`, `desert`, `ior_maritime`, or `monsoon_belt`
- `--fault-chance`: Probability of fault injection (0.0 to 1.0)
- `--airframe-id`: Optional persistent aircraft ID (default: `AIRFRAME-SIH26054-001`)

This generates ~2000 telemetry packets (one every 2–3 seconds, matching real-time pacing).

### 4. Evaluate Physics Layer (Live Mode)

In a **separate terminal**, start the physics evaluator in live mode while the flight is generating:

```bash
python physics_layer.py --flight-id FL-2026-08-30-001 --live
```

The evaluator polls for new telemetry every 1–2 seconds and writes debounced health status.

### 5. Launch Dashboard

In a **third terminal**, start the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

Then open `http://localhost:8501` in your browser.

- **Live Flight** tab: Watch real-time telemetry and health status
- **Flight History** tab: Scrub through completed flights
- **Maintenance** tab: View icing and fault advisories

---

## Project Structure

```
SIH26054/
├── database.py                 # Schema & database utilities
├── config.py                   # Engine & environment parameters
├── utils.py                    # OU processes, utilities, debouncing
├── environmental_model.py      # Humidity, precipitation, dust, corrosion (STEP 3)
├── environmental_physics.py    # Density altitude, icing, fault attribution (STEP 4)
│
├── generate_telemetry.py       # STEP 1-3: Telemetry generation
├── physics_layer.py            # STEP 2-4: Physics evaluation
├── dashboard.py                # STEP 5-7: Streamlit dashboard
│
├── validate.py                 # Reproducibility & debouncing tests
├── requirements.txt            # Python dependencies
└── plan.md                      # Detailed implementation plan
```

---

## The 7-Step Build Order

### **STEP 1 & 2: Core Engine-Only Pipeline** ✅

1. **Schema + generate_telemetry.py skeleton**
   - Seeded, reproducible flight generation
   - OU processes for smooth sensor noise
   - Fault injection (scheduled once per flight, not per-packet)
   - Engine-only parameters: RPM, CHT, EGT, oil temp/pressure, fuel flow, vibration, battery, AFR

2. **physics_layer.py skeleton**
   - Compute expected values based on phase/RPM
   - Calculate deviations
   - **Debounce status** (the flicker fix: require 3 of 5 packets to agree before changing status)
   - Compute subsystem health and overall condition

**Verify with:**
```bash
python validate.py
```

### **STEP 3: Environmental Fields** ✅

- **In generate_telemetry.py:** add `EnvironmentalModel` to generate:
  - Humidity (climate-zone dependent, decreases with altitude)
  - Pressure altitude
  - Precipitation events
  - Filter service hours (accumulates, zone-dependent)
  - Maritime corrosion hours (accumulates for maritime zones)

### **STEP 4: Environmental Physics** ✅

- **In physics_layer.py:** add `EnvironmentalPhysics` to compute:
  - **Density altitude** (DA = PA + 120 × (OAT − (15 − 1.98 × PA/1000))) and power-loss correction
  - **Icing risk** classification (HIGH if 0–15°C and RH ≥ 50%)
  - **Fault attribution override** (e.g., low fuel flow + icing → "probable induction icing")
  - **Dust/filter degradation** of fuel flow (unfitted placeholder coefficient)
  - **Corrosion index** (slow-moving, per-airframe advisory)

### **STEP 5: Live Dashboard View** ✅

- Real-time status banner (NORMAL / CAUTION / CRITICAL)
- Parameter gauges grouped by subsystem
- Subsystem health scores (0–100%)
- Icing advisory chip (separate from health)
- Trend chart for worst subsystem

### **STEP 6: Historical View** ✅

- Flight picker (list of completed flights)
- Time scrubber (replay mission time)
- Same gauge/health rendering as live view

### **STEP 7: Polish** ✅

- Trend chart selection
- Maintenance advisory panel (corrosion per airframe)
- Color-coded status indicators
- UI/UX refinement

---

## Key Design Decisions

### **1. Reproducibility via Seeding**

Every flight gets a deterministic seed derived from its `flight_id`:

```python
seed = hash(flight_id)
rng = random.Random(seed)
```

- Same flight ID → identical telemetry (byte-for-byte reproducible)
- Useful for testing, validation, and replay

### **2. Consistency: The Debounce Fix**

Raw sensor noise can make status flicker packet-to-packet (e.g., a value hovering at a threshold can appear NORMAL → CAUTION → NORMAL repeatedly).

**Solution:** Debounced status uses a rolling window (default: 5 packets, require 3 in agreement) before confirming a status change. A temporary noise spike doesn't flip the dashboard status; a real, sustained trend does within ~10–15 seconds.

**Two-column design:**
- `raw_status` — per-packet, undebounced (for deep replay analysis)
- `status` — debounced, dashboard-facing (for operator display)

### **3. Environmental Corrections Are Separate**

The health score is purely acute (engine condition), never mixed with long-horizon advisories:
- **Health rollup** → subsystem scores → overall status (NORMAL/CAUTION/CRITICAL)
- **Icing advisory** → shown as a banner, not a health deduction
- **Corrosion index** → shown in maintenance panel, cross-flight tracking

This matters for pilot/operator understanding: a HIGH icing advisory doesn't mean the engine is failing; it means icing conditions exist, and the pilot must adapt procedures.

### **4. Faults Are Scheduled, Not Rolled Per-Packet**

Once a flight starts, fault injection is decided immediately:
```
if rng.random() < fault_chance:
    fault_parameter = "oil_pressure_psi"
    fault_start_time = scheduled_time + jitter
    fault_severity = -0.2 psi/s
```

A fault, once active, is a **monotonic trend** (e.g., oil pressure drops linearly over time), not a random jump per packet. This ensures a fault looks consistent and believable.

### **5. Cross-Flight Airframe Tracking**

`maritime_hours_cumulative` and `corrosion_index` persist across flights via a shared `airframe_id`:

```python
airframe_id = "AIRFRAME-SIH26054-001"  # same aircraft across multiple flights
```

Corrosion accumulates in the database across all flights for that airframe, enabling long-horizon maintenance planning.

---

## Configuration

Edit `config.py` to adjust:

- **Engine parameters** (Rotax 914 baseline — can swap for O-320 naturally-aspirated)
- **Mission profile** (phases, durations, RPM targets)
- **Climate zones** (temperature, humidity, dust exposure rates)
- **Icing risk thresholds** (LOW/MODERATE/HIGH envelope)
- **Debounce window size** (default: 5 packets, 3-vote majority)
- **Fault profiles** (parameter, severity, onset time)

---

## Validation & Testing

### Reproducibility Test

```bash
python validate.py
```

Generates the same flight twice and verifies all packets are identical (byte-for-byte when rounded to 2 decimals).

### Live + Replay Workflow

```bash
# Terminal 1: Generate a flight
python generate_telemetry.py --flight-id FL-TEST-001 --zone desert --fault-chance 0.3 &

# Terminal 2: Evaluate in live mode
sleep 5  # wait for first telemetry packets
python physics_layer.py --flight-id FL-TEST-001 --live &

# Terminal 3: Dashboard
streamlit run dashboard.py

# After flight completes, replay in physics_layer:
python physics_layer.py --flight-id FL-TEST-001 --replay
```

---

## Database Schema

### `flights`
```sql
CREATE TABLE flights (
    flight_id TEXT PRIMARY KEY,
    start_time TEXT,
    climate_zone TEXT,
    seed INTEGER,
    fault_injected TEXT,        -- NULL or parameter name
    status TEXT,                -- 'in_progress' | 'complete'
    airframe_id TEXT
);
```

### `telemetry`
```sql
CREATE TABLE telemetry (
    flight_id TEXT,
    mission_time_s REAL,
    timestamp TEXT,
    phase TEXT,
    rpm REAL, cht_c REAL, egt_c REAL, ...,    -- engine channels
    humidity_pct REAL, pressure_altitude_m REAL, precipitation INTEGER,
    hours_since_filter_service REAL, maritime_hours_cumulative REAL,
    climate_zone TEXT
);
```

### `evaluations`
```sql
CREATE TABLE evaluations (
    flight_id TEXT,
    mission_time_s REAL,
    timestamp TEXT,
    parameter TEXT,
    actual REAL, expected REAL, deviation_pct REAL,
    raw_status TEXT,           -- undebounced
    status TEXT                -- debounced
);
```

### `flight_condition`
```sql
CREATE TABLE flight_condition (
    flight_id TEXT, mission_time_s REAL, timestamp TEXT,
    subsystem_health_json TEXT,   -- {"combustion": 96.2, ...}
    overall_status TEXT,
    icing_advisory TEXT,
    fault_category TEXT
);
```

### `corrosion_tracking`
```sql
CREATE TABLE corrosion_tracking (
    airframe_id TEXT PRIMARY KEY,
    corrosion_index REAL,
    last_updated TEXT
);
```

---

## API / Programmatic Usage

### Generate a Flight Programmatically

```python
from generate_telemetry import FlightGenerator

gen = FlightGenerator(
    flight_id="FL-PROG-001",
    climate_zone="ior_maritime",
    fault_chance=0.5,
    airframe_id="AIRFRAME-TEST"
)
gen.run_flight()  # writes to database
```

### Evaluate Physics Programmatically

```python
from physics_layer import PhysicsEvaluator

eval = PhysicsEvaluator("FL-PROG-001", is_live=False)
eval.process_flight()  # replay mode - evaluates complete flight
```

### Query Results

```python
import sqlite3

conn = sqlite3.connect("digital_twin.db")
cursor = conn.cursor()

# Get latest telemetry
cursor.execute(
    "SELECT * FROM telemetry WHERE flight_id = ? ORDER BY mission_time_s DESC LIMIT 1",
    ("FL-PROG-001",)
)
latest = cursor.fetchone()

# Get subsystem health trend
cursor.execute(
    "SELECT mission_time_s, subsystem_health_json FROM flight_condition "
    "WHERE flight_id = ? ORDER BY mission_time_s ASC",
    ("FL-PROG-001",)
)
health_trend = cursor.fetchall()
```

---

## Open Decisions (from plan.md)

1. **Concurrent-write handling:** SQLite's write-locking is adequate for ~0.4 Hz packet rates (2–3 s intervals). For sub-second rates, upgrade to PostgreSQL.

2. **Airframe identity:** Cross-flight tracking uses a stable `airframe_id`. Set this once per simulated aircraft to track maintenance metrics across missions.

3. **Engine profile:** Rotax 914 (turbocharged) is the baseline. Naturally-aspirated profiles (O-320) are configured but not wired into the live pipeline by default. Adjust `POWER_LOSS_CORRECTION` and `TURBOCHARGED_RATED_ALT_FT` in `config.py` to switch.

---

## Examples

### Example 1: Desert Mission with Dust Monitoring

```bash
python generate_telemetry.py --flight-id FL-DESERT-HIGH-DUST \
    --zone desert \
    --fault-chance 0.2 \
    --airframe-id AIRFRAME-DUST-TEST

python physics_layer.py --flight-id FL-DESERT-HIGH-DUST --replay
```

The physics layer will show increasing dust-related fuel flow degradation as `hours_since_filter_service` accumulates.

### Example 2: Maritime Zone with Icing and Corrosion

```bash
python generate_telemetry.py --flight-id FL-MARITIME-ICING \
    --zone ior_maritime \
    --fault-chance 0.3 \
    --airframe-id AIRFRAME-CORROSION-TRACKER

python physics_layer.py --flight-id FL-MARITIME-ICING --replay
```

Dashboard will show:
- HIGH icing advisory if 0–15°C and RH ≥ 50%
- Corrosion index accumulating per airframe in maintenance panel

### Example 3: Reproducibility Verification

```bash
# Run same flight twice
python generate_telemetry.py --flight-id FL-REPRO-TEST-001 \
    --zone himalayan --fault-chance 0.1

rm digital_twin.db
python database.py

python generate_telemetry.py --flight-id FL-REPRO-TEST-001 \
    --zone himalayan --fault-chance 0.1

# Query and compare: every packet should be identical
```

---

## Troubleshooting

### Q: Dashboard shows "No data available"
**A:** Ensure `generate_telemetry.py` and `physics_layer.py` are running or have completed. Check the database exists: `ls digital_twin.db`

### Q: Status keeps flicker between CAUTION and NORMAL
**A:** This is the problem the debounce fix solves. If it's still happening, check:
1. `DEBOUNCE_CONFIG["window_packets"]` (default: 5)
2. `DEBOUNCE_CONFIG["threshold_packets"]` (default: 3)
3. Status thresholds in `raw_status_from_deviation()`

### Q: Fault isn't showing up
**A:** 
1. Check `fault_chance` is > 0
2. Verify fault time hasn't passed: `fault_start_s` should be between 0 and flight duration
3. Confirm fault parameter is one of the engine channels in `config.py`

### Q: Environmental fields are all zeros
**A:** Run `generate_telemetry.py` (Step 3) with `environmental_model.py` imported. Older versions use placeholders.

---

## Next Steps / Future Enhancements

1. **PostgreSQL backend** — for production (remove SQLite write-lock constraints)
2. **Real sensor data ingestion** — replace simulated data with actual flight logs
3. **ML-based anomaly detection** — replace threshold-based classification
4. **Mobile app** — remote monitoring of live flights
5. **Integration with flight control systems** — real-time alerts to autopilot
6. **Multi-aircraft coordination** — track fleet-wide health and maintenance

---

## References

- **Engine Parameters & Physics Model:** `Engine_Parameters_and_Physics_Model.pdf`
- **Climate & Environmental Parameters:** `Climate_Environmental_Parameters.pdf`
- **Implementation Plan:** [plan.md](plan.md)

---

## License & Attribution

This project is part of the SIH 2024-26 (Smart India Hackathon) challenge submission for Digital Twin for MALE UAVs.

---

**Questions?** Review the detailed plan in [plan.md](plan.md) or inspect the inline code comments in each module.

**Ready to fly? 🚀**
```bash
python generate_telemetry.py --flight-id FL-2026-08-30-DEMO --zone ior_maritime --fault-chance 0.4 &
sleep 5
python physics_layer.py --flight-id FL-2026-08-30-DEMO --live &
streamlit run dashboard.py
```
