# AI-Enabled Digital Twin for UAV Piston Engines — Detailed Execution Plan

This expands PLAN.pdf into something you can actually build from: what data lives where, what each module computes, worked examples, and what "done" looks like per phase.

---

## 1. The core idea in one sentence

You keep two parallel streams for the same engine at the same instant — **what the engine is actually doing** (live sensor values) and **what the engine should be doing** (a physics-derived expectation) — and the *gap* between them is where all the intelligence comes from: health scores, fault alerts, and remaining-life predictions.

---

## 2. Data layer — what a sensor reading actually looks like

Since there's no real DRDO engine data, you generate realistic synthetic telemetry. Design the schema first — everything downstream depends on it.

**Example single telemetry packet (one engine, one timestamp):**
```json
{
  "timestamp": "2026-08-28T10:15:32Z",
  "engine_id": "ENG-04",
  "rpm": 4200,
  "cht_c": 178.5,
  "egt_c": 812.0,
  "oil_temp_c": 92.3,
  "oil_pressure_psi": 58.1,
  "fuel_flow_lph": 14.2,
  "vibration_g": 0.31,
  "battery_voltage": 13.8,
  "injection_timing_deg": 22.5,
  "altitude_m": 4200,
  "ambient_temp_c": 18.0
}
```

**Generating synthetic data (Phase 1):**
- Start from a "healthy baseline" function per parameter as a function of RPM (e.g. `oil_temp_c ≈ 60 + 0.008 × rpm + noise`).
- Add scenario layers on top: `cruise`, `climb`, `high-altitude`, `hot-weather`.
- Add **degradation injections** — slowly drift one or more parameters over hours of simulated flight (e.g. oil pressure decaying 0.5% per simulated hour to mimic a developing leak), so your ML models have something real to learn from later.
- Store as a time series keyed by `(engine_id, timestamp)` in SQLite — this becomes your training set *and* your replay archive.

This is the one piece of engineering that everything else is built on, so it's worth spending real time on realism (correlated noise, not just random jitter; parameters that move together the way real physics would).

---

## 3. Digital twin core — where "expected" comes from

This is the physics-informed layer DRDO explicitly asks for. It doesn't need to be a full thermodynamic simulation — a set of calibrated rules is enough for MVP.

**Example rule (expected oil temperature):**
```python
def expected_oil_temp(rpm, ambient_temp, altitude):
    base = 55 + 0.009 * rpm          # RPM contributes heat
    altitude_correction = -0.002 * altitude   # thinner air cools less at altitude... 
    return base + 0.6 * ambient_temp + altitude_correction
```
At `rpm=4200, ambient=18, altitude=4200`: expected ≈ 55 + 37.8 + 10.8 − 8.4 ≈ **95.2°C**.
The live reading was 92.3°C — a small negative deviation, within normal band. If live were 118°C, that's a 24% deviation — flagged.

**Compare step output (per parameter, per timestamp):**
```json
{"parameter": "oil_temp_c", "expected": 95.2, "actual": 92.3, "deviation_pct": -3.0, "status": "normal"}
```
Do this for every monitored parameter → this is the raw material for both the health index and the anomaly detector.

---

## 4. Health monitoring — turning deviations into one number

A **health index** is just a weighted aggregate of deviations, scaled to something a non-technical judge or operator reads at a glance.

**Example (simplified):**
```
subsystem_health = 100 − Σ(weight_i × |deviation_pct_i|)
```
- Lubrication subsystem: `oil_temp_c` (weight 0.4) + `oil_pressure_psi` (weight 0.6)
- If oil temp deviation = 3%, oil pressure deviation = 15% (pressure dropping) →
  `health = 100 − (0.4×3 + 0.6×15) = 100 − 10.2 = 89.8` → shown on dashboard as **"Lubrication: 90% — Nominal"**, trending down.

This is what makes the dashboard readable at a glance instead of forcing the viewer to parse raw numbers.

---

## 5. Fault detection — Isolation Forest, concretely

You're not classifying *known* fault types initially — you're detecting *"this doesn't look like normal engine behavior."*

**Workflow:**
1. Train `IsolationForest` on your synthetic **healthy-only** data (multi-dimensional: RPM, CHT, EGT, oil temp/pressure, vibration, fuel flow — as a feature vector per timestamp).
2. Feed live (or injected-fault) readings through the trained model.
3. Model outputs an anomaly score; below a threshold → flagged.

```python
from sklearn.ensemble import IsolationForest
model = IsolationForest(contamination=0.02, random_state=42)
model.fit(healthy_data[features])
scores = model.decision_function(live_window[features])
is_anomaly = scores < -0.1   # tune threshold on validation data
```

**Example alert this produces:**
> ⚠ Anomaly detected 10:16:04 — vibration_g=0.89 (baseline ~0.3), EGT rising 4°C/min. Pattern consistent with **injector abnormality**. Confidence: high.

Map anomaly clusters to fault *categories* (misfire, injector issue, sensor drift, lubrication problem, overheating trend, combustion instability) by looking at *which* features deviate together — that mapping is a rule layer on top of the raw anomaly score, and it's what makes the alert useful instead of just "something's wrong."

---

## 6. RUL estimation — the predictive piece

Remaining Useful Life turns "there's a problem" into "you have about this much time before it matters."

**Approach for MVP (regression on degradation trend):**
- For each injected-degradation synthetic run, you *know* the ground-truth time-to-failure (you generated it).
- Extract trend features per time window: rate of change of oil pressure, vibration trend slope, health index slope.
- Train a regressor (start with `RandomForestRegressor` or `GradientBoostingRegressor`; upgrade to LSTM later if time allows) to predict hours-remaining from these trend features.

**Example output:**
```json
{"engine_id": "ENG-04", "subsystem": "lubrication", "predicted_rul_hours": 14.5, "confidence_interval": [11, 19]}
```
Dashboard turns this into: **"Lubrication system — estimated 14.5 flight hours to threshold. Recommend inspection before next 3 missions."**

This is the DRDO ask that separates you from "reactive threshold monitoring" — you're not just detecting failure, you're forecasting it.

---

## 7. Simulation & replay — value for judges specifically

This is often underbuilt because it feels like a "nice to have," but it's what makes the demo feel real instead of theoretical.

- **Mission-profile simulator**: let a user pick "high-altitude ISR mission over Ladakh" or "maritime patrol, hot-humid" and watch the twin generate a full flight's telemetry + health trajectory in fast-forward. This is your **live demo centerpiece** — nothing convinces a judge like watching a fault develop and get caught in real time.
- **Historical replay**: pull a stored mission from SQLite and scrub through it on the dashboard, exactly like a flight-data recorder review. Useful for post-flight debriefs and for showing a fault you already caught, calmly, without needing to fake live data on stage.

---

## 8. Dashboard — what actually needs to be on screen

Prioritize *legibility* over *feature count* for the demo:
1. Live parameter readout (raw values, small multi-line chart)
2. Subsystem health gauges (the aggregated numbers from §4) — this is what a judge's eye goes to first
3. Active fault alerts, with the category + confidence from §5
4. RUL / degradation trend chart from §6 — a line trending down toward a threshold is instantly legible
5. Mission selector + replay control from §7

---

## 9. End-to-end example: one fault, start to finish

1. Synthetic generator injects a slow oil-pressure leak into ENG-04's data starting at simulated hour 40.
2. Ingestion streams it in via MQTT to FastAPI.
3. Twin core compares live oil pressure (58.1 → drifting to 51.0 over 2 hours) against the expected-behavior model (~59 psi at that RPM/altitude) → deviation grows from 3% to 14%.
4. Health module: Lubrication subsystem health drops from 96 → 78.
5. Isolation Forest flags the reading as anomalous once deviation crosses the trained threshold (~hour 41.5).
6. RUL model, seeing the pressure-decay slope, estimates 14.5 hours remaining before critical threshold.
7. Dashboard shows: health gauge amber, fault alert "lubrication — pressure trending low," RUL countdown, and a degradation chart.
8. Maintenance recommendation surfaces: "Inspect oil system before next 2 missions."

That whole chain — sensor → physics comparison → health → anomaly → RUL → recommendation — **is the product.** Every phase in PLAN.pdf is building one link of this chain.

---

## 10. Value mapping — where each output comes from

| Output shown to user | Computed from | Depends on |
|---|---|---|
| Raw parameter readout | Ingestion layer, straight passthrough | Phase 1 |
| Subsystem health % | Physics model vs live comparison, weighted | Phase 2 |
| Fault alert + category | Isolation Forest anomaly score + feature-deviation pattern | Phase 3 |
| RUL estimate | Regression/LSTM on degradation trend features | Phase 4 |
| Mission simulation | Physics model run forward under a chosen profile, no live data needed | Phase 5 |
| Historical replay | Stored SQLite time series, replayed through the same dashboard views | Phase 5 |

---

## 11. Practical build order (condensed from PLAN.pdf's phases)

1. **Schema + synthetic generator first** — nothing else can be tested without this.
2. **Physics rules** — start with 2–3 parameters (oil temp, CHT, EGT) fully working before adding the rest; a shallow-but-complete pipeline beats a deep-but-partial one for a hackathon demo.
3. **Health index** — simple weighted formula is fine; don't over-engineer.
4. **Isolation Forest** — train on your generator's "healthy" mode; validate against your "faulty" injections.
5. **RUL regressor** — only after fault detection works, since it reuses the same feature pipeline.
6. **Simulation/replay + dashboard polish** — save real time for this; it's what the judges actually watch.

---

## 12. What to say explicitly in the pitch (from the PDF's own honest-scoping section)

- Data is realistic synthetic data, explicitly framed as "recalibrated with real operational data upon deployment."
- RUL/health outputs are **decision support**, not autonomous control — operator/GCS always confirms.
- System is engine-agnostic — calibration table per engine type, not hardcoded to one platform.

These aren't weaknesses to hide — stating them upfront reads as engineering maturity to DRDO judges, who deal with certification and safety framing constantly.
