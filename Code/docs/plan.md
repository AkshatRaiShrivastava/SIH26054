# Digital Twin Pipeline — Implementation Plan (Rotax 914 baseline)

This plan covers three things that work together: two Python files (data generation, physics evaluation) and one dashboard that reads what they produce. Rotax 914 is the baseline engine profile (turbocharged — matches the Heron-class MALE UAV reference used earlier). Environmental parameters come from `Climate_Environmental_Parameters.pdf`; engine parameters come from `Engine_Parameters_and_Physics_Model.pdf`.

```
generate_telemetry.py  --(writes packets to SQLite, one flight at a time)-->
physics_layer.py       --(reads packets, writes evaluated conditions back)-->
dashboard.py            --(reads both tables: live tail + full history)
```

All three talk to each other **only through the database** — no direct function calls between files, no in-memory hand-off. This is deliberate: it's what makes "past flight data" and "live dashboard" the same code path (one reads recent rows, the other reads a date-range of rows), and it's what makes the consistency requirement below actually enforceable.

---

## 0. The consistency requirement — read this before building anything

> "packet should be consistent for that flight so it won't look like one packet has an issue and the next is normal"

This is the single most important constraint in this plan, so it gets its own section instead of being buried in File 1.

**Two separate problems produce the flicker you're describing, and they need two separate fixes:**

**Problem A — non-reproducible, memoryless generation.** If each packet is generated independently (fresh random numbers, no memory of the previous packet or of what fault was scheduled), a fault can appear to "flash" in and out because nothing is enforcing continuity between packets.
**Fix:** every flight gets a `flight_id` and a **seed derived from it** (`seed = hash(flight_id)`). All randomness for that flight — noise, fault timing, fault severity — is drawn from one `random.Random(seed)` instance created once at the start of the flight and threaded through every packet. Re-running the same `flight_id` reproduces the exact same telemetry, byte for byte. This also means faults are **scheduled once, up front**, not re-rolled per packet — see File 1, §1.3.

**Problem B — a real (small) fluctuation crossing a hard threshold.** Even with perfectly smooth underlying physics, sensor noise means a value can tick 4.9% → 5.1% → 4.8% right at a caution boundary, and a naive classifier flips status every packet even though nothing meaningful changed.
**Fix:** status classification in File 2 is **debounced**, not evaluated packet-by-packet in isolation — see File 2, §2.3.

Both fixes are cheap. Skipping either one is what produces exactly the symptom you flagged.

---

## FILE 1 — `generate_telemetry.py`

### 1.1 Purpose
For one simulated flight, produce a full, internally-consistent, reproducible sequence of telemetry packets — engine parameters *and* environmental parameters — and write them to the database as they're generated (not all at once at the end), so File 2 and the dashboard can consume them as a live stream.

### 1.2 Parameters this file must generate

**Engine channels** (from the engine-parameters document, Rotax 912/914 profile):

| Parameter | Field name | Unit |
|---|---|---|
| Engine speed | `rpm` | rpm |
| Cylinder head temp | `cht_c` | °C |
| Exhaust gas temp | `egt_c` | °C |
| Oil temperature | `oil_temp_c` | °C |
| Oil pressure | `oil_pressure_psi` | psi |
| Fuel flow | `fuel_flow_lph` | L/h |
| Vibration | `vibration_g` | g (RMS) |
| Battery/alternator voltage | `battery_v` | V |
| Air/fuel ratio | `afr` | ratio |
| Altitude | `altitude_m` | m |
| Ambient temperature | `ambient_temp_c` | °C |

**Environmental channels** (new — from the climate/environmental document, §2):

| Parameter | Field name | Unit | Why it's generated, not derived |
|---|---|---|---|
| Relative humidity | `humidity_pct` | % | Independent driver (icing risk, minor density effect); not derivable from temp/altitude alone |
| Pressure altitude | `pressure_altitude_m` | m | Feeds the density-altitude formula alongside `ambient_temp_c` |
| Region/mission-zone flag | `climate_zone` | enum | One of: `himalayan`, `desert`, `ior_maritime`, `monsoon_belt` — drives which of the four regional profiles (climate doc §4) is active |
| Precipitation flag | `precipitation` | bool | Monsoon-season operating-profile flag (climate doc §3.2, §3.4) |
| Cumulative flight hours since filter service | `hours_since_filter_service` | hours | Feeds the dust/filter-loading drift (climate doc §3.3) — this is a **flight-history** field, not a per-packet random value: it should increment consistently across a flight and persist across flights for the same simulated airframe |
| Maritime mission hours (cumulative) | `maritime_hours_cumulative` | hours | Feeds the corrosion index (climate doc §3.4) — same cross-flight persistence note as above |

**Derived/computed per packet (not stored as independent random fields — computed from the above using the physics-doc formulas, then noise-perturbed the same way engine channels are):** `density_altitude_m`, `icing_risk` (LOW/MODERATE/HIGH).

### 1.3 How a flight is generated — consistency mechanics

1. **Flight setup (once, before the packet loop):**
   - `flight_id` assigned (e.g. `FL-{date}-{sequence}`).
   - `rng = random.Random(seed_from(flight_id))` — everything below draws from this one generator.
   - Route + climate zone selected (reuse `route_and_climate()` from the earlier synthetic-telemetry module) → this sets `climate_zone` for the whole flight, not per packet.
   - Mission profile built (reuse `mission_profile()`) → phase timeline is fixed for the flight.
   - **Faults are scheduled here, once**, not decided per packet: `rng.random() < fault_probability` decides *if* this flight has a fault; if so, `start_s`, `parameter`, and `rate_per_s` are drawn once and held fixed for the rest of the flight. A fault, once scheduled, is a deterministic function of elapsed time — it never "un-happens" partway through a flight.
   - Per-parameter `OUProcess` instances are created once, seeded from `rng` — their internal state (`self.x`) persists and is updated tick-by-tick for the whole flight. This is what makes the noise a smooth *trajectory* instead of independent jitter — already correct in the earlier synthetic-telemetry design, just calling it out explicitly here since it's central to the consistency requirement.

2. **Per-packet loop** (every simulated tick):
   - Compute mission phase, position, base climate (ambient temp, humidity) for this instant — from the fixed route/mission timeline, not re-rolled.
   - Compute engine expected values (physics formulas) from the current RPM/altitude/ambient.
   - Apply the *same* `OUProcess` step + fault-trend offset used for every prior packet this flight — continuing the trajectory, not restarting it.
   - Compute environmental derived fields: density altitude, icing risk flag (from formulas in §2.2 below — these live in File 1 only as far as generating the *inputs*; the actual risk-flag computation is physics-layer logic and belongs in File 2, so File 1 only needs to generate `humidity_pct` and `pressure_altitude_m` here, not `icing_risk` itself).
   - Increment `hours_since_filter_service` and, if `climate_zone == ior_maritime`, `maritime_hours_cumulative`.
   - Write the packet to the database immediately (not buffered) so File 2 can pick it up within the packet interval.
   - Sleep 2–3 s (randomized from `rng`, not from the global `random` module — same reproducibility reasoning) before the next packet, matching the live-pacing behavior already built.

3. **Flight teardown:** mark the flight row `status = complete` in the database when the mission profile ends, so the dashboard's flight picker knows it's a finished, browsable flight rather than one still in progress.

### 1.4 Storage — proposed schema

```sql
CREATE TABLE flights (
    flight_id TEXT PRIMARY KEY,
    start_time TEXT,
    climate_zone TEXT,
    seed INTEGER,
    fault_injected TEXT,        -- NULL, or e.g. "oil_pressure_psi"
    status TEXT                 -- 'in_progress' | 'complete'
);

CREATE TABLE telemetry (
    flight_id TEXT,
    mission_time_s REAL,
    timestamp TEXT,
    phase TEXT,
    -- engine channels
    rpm REAL, cht_c REAL, egt_c REAL, oil_temp_c REAL, oil_pressure_psi REAL,
    fuel_flow_lph REAL, vibration_g REAL, battery_v REAL, afr REAL,
    altitude_m REAL, ambient_temp_c REAL,
    -- environmental channels
    humidity_pct REAL, pressure_altitude_m REAL, precipitation INTEGER,
    hours_since_filter_service REAL, maritime_hours_cumulative REAL,
    FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
);
```

Both `flights` and `telemetry` are append-only during a run — File 2 and the dashboard only ever `SELECT`, never write to these two tables (File 2 writes to its own `evaluations` table — see below).

### 1.5 What "running the main file" does, end to end

```
python generate_telemetry.py --flight-id FL-2026-08-30-01 --zone ior_maritime --fault-chance 0.4
```
1. Insert a row into `flights`.
2. Run the per-packet loop from §1.3, inserting one `telemetry` row every 2–3 real seconds.
3. Mark the flight `complete` when the mission profile ends.
4. Exit. (File 2 can be running concurrently the whole time, tailing the `telemetry` table — see below.)

---

## FILE 2 — `physics_layer.py`

### 2.1 Purpose
Independently recompute what every engine channel *should* read, apply the environmental corrections from the climate document, compare against what File 1 actually generated, and produce a debounced, human-readable condition report — written back to the database so the dashboard can show it live or pull it up historically.

### 2.2 What gets recomputed, and what's new versus the engine-only version

Everything from the original `physics_layer.py` (expected CHT/EGT/oil temp/oil pressure/fuel flow/vibration) is unchanged. New for this version, straight from the climate document:

- **Density altitude** (§3.1 of climate doc) — replaces plain geometric altitude as the input to the power-loss/expected-value chain where it matters:
  `DA = PA + 120 × (OAT − (15 − 1.98 × PA/1000))`
  Branch on engine variant: since this pipeline's baseline is the turbocharged Rotax 914, the naturally-aspirated ~3 hp/1,000 ft power-loss curve does **not** apply directly — the twin should note that the 914's turbo compensates up to its rated altitude, and only apply the naturally-aspirated power-loss correction if a naturally-aspirated profile (e.g. the O-320 profile) is active. This branch should be a config flag read at flight setup, not hardcoded.

- **Icing risk index** (§3.2 of climate doc) — a context flag, not a fault:
  `HIGH if 0°C ≤ OAT ≤ 38°C and RH ≥ 50%`, `MODERATE if RH between 30–50%` in the same temp band, else `LOW`.
  This is the piece that changes how fault *attribution* works: if `icing_risk == HIGH` and fuel flow is trending below expected with RPM/EGT drifting consistently with partial induction blockage, the fault-category label should be **"probable induction icing"**, not "injector abnormality" — this is a lookup/override step applied *after* the normal deviation classification, not a replacement for it.

- **Dust/filter-loading drift** (§3.3) — a slow multiplicative correction on expected fuel flow:
  `filter_health_pct = 100 − k_dust × dust_exposure_index`
  `expected_fuel_flow_adj = expected_fuel_flow × (1 − 0.002 × (100 − filter_health_pct))`
  `dust_exposure_index` is a function of `climate_zone` (desert = high accumulation rate) and `hours_since_filter_service` from the telemetry row. `k_dust` and the `0.002` coefficient are unfitted placeholders, per the climate doc's own limitations section — flag them as such in code comments, don't present them as sourced.

- **Corrosion index** (§3.4) — does **not** feed the real-time deviation pipeline at all. It's a separate, slow-moving score computed from `maritime_hours_cumulative` and accumulated across flights (reads/writes a running total keyed by a simulated airframe ID, not by `flight_id`) — this is a maintenance-advisory output, not a per-packet condition.

### 2.3 Deviation → status, with debounce (this is the flicker fix)

Do **not** classify status from a single packet's deviation in isolation. Instead:

1. Maintain a short rolling window (e.g. last 5 packets, ~10–15 real seconds) per parameter, per flight.
2. A status change (`normal → caution`, `caution → critical`, or any downgrade) only takes effect once **N consecutive packets** (e.g. 3 of the last 5) agree on the new status. A single noisy packet touching a threshold doesn't flip the displayed status; a real, sustained trend does within ~10–15 seconds — fast enough to still feel live, slow enough not to flicker.
3. Store both the **raw per-packet deviation** (for the historical/replay view, where you may want to see the actual noise) and the **debounced status** (for the live banner and the health score) — two different columns, not one overwriting the other.

This directly addresses the consistency complaint: a fault, once real, will show a stable, worsening status; ordinary sensor noise will not cause the dashboard to jump between "normal" and "critical" packet to packet.

### 2.4 Subsystem health & overall condition — now with an advisory layer

Reuse the subsystem rollup from the original `physics_layer.py` (combustion / lubrication / fuel_system / mechanical) unchanged for **acute** condition. Add a parallel, separate **advisory layer** that is never mixed into the health-score math:

- `icing_advisory`: HIGH / MODERATE / LOW (from §2.2 above) — shown as a banner, not a health deduction, since (per the climate doc's worked example) an aircraft can have a HIGH icing advisory while every real-time reading is nominal.
- `corrosion_trend`: a slowly-rising score shown only on the maintenance-advisory panel, not the live health gauges.

This split matters for the dashboard design in §4 — acute health and long-horizon advisories are visually different things and should never be collapsed into one number.

### 2.5 Storage — evaluations table

```sql
CREATE TABLE evaluations (
    flight_id TEXT,
    mission_time_s REAL,
    timestamp TEXT,
    parameter TEXT,
    actual REAL, expected REAL, deviation_pct REAL,
    raw_status TEXT,          -- per-packet, undebounced
    status TEXT,              -- debounced, dashboard-facing
    FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
);

CREATE TABLE flight_condition (
    flight_id TEXT, mission_time_s REAL, timestamp TEXT,
    subsystem_health_json TEXT,   -- {"combustion": 96.2, "lubrication": 83.1, ...}
    overall_status TEXT,
    icing_advisory TEXT,
    fault_category TEXT           -- NULL or e.g. "probable induction icing"
);

CREATE TABLE corrosion_tracking (
    airframe_id TEXT PRIMARY KEY,
    corrosion_index REAL,
    last_updated TEXT
);
```

### 2.6 How it's invoked

Two modes, same evaluation code underneath:
- **Live mode:** `python physics_layer.py --flight-id FL-... --live` — polls the `telemetry` table for rows newer than the last one it processed (every 1–2 s), evaluates each, writes to `evaluations`/`flight_condition`. Runs concurrently with File 1.
- **Backfill/replay mode:** `python physics_layer.py --flight-id FL-... --replay` — processes an already-complete flight's full `telemetry` history in one pass, useful for re-running the physics layer against old flights after a formula/threshold change without regenerating telemetry.

---

## DATA LAYER — how the dashboard reads both files' output

The dashboard never talks to File 1 or File 2 directly — it only queries SQLite:
- **Live view:** `SELECT ... FROM telemetry WHERE flight_id = ? ORDER BY mission_time_s DESC LIMIT 1` joined against the matching `flight_condition` row, polled every 2–3 s (matching the packet interval) to stay in sync without polling faster than new data can arrive.
- **Historical view:** same queries, but for a *selected* `flight_id` with `status = 'complete'`, and no polling loop — just a scrub/replay control that steps through `mission_time_s`.

This is why the two-file, database-mediated design matters: "live" and "past flight" are the same dashboard code, parameterized by which `flight_id` and whether polling is active — not two separate dashboards.

---

## DASHBOARD — `dashboard.py`

### 4.1 Tech choice
Streamlit — matches the "fast path" option from the original tech-stack decision (Python-only, good enough for a judged demo, no separate frontend build). Streamlit's rerun-on-interval pattern (`st.fragment(run_every="2s")` or a manual polling loop) maps directly onto the 2–3 s packet cadence already established.

### 4.2 Live view — layout
- **Top banner:** overall UAV status (NORMAL / CAUTION / CRITICAL, from `flight_condition.overall_status`), large and color-coded — this is the first thing a judge's eye should hit.
- **Icing advisory chip:** separate small banner element, shown only when `icing_advisory != LOW` — visually distinct from the main status banner per §2.4's split.
- **Parameter bars/gauges:** one bar or gauge per engine channel (`st.progress` or a small `st.metric` + colored bar, or a gauge chart via `plotly`), each showing: current value, expected value marker, and a color reflecting `status` (green/amber/red) — this is the "virtual bars" requirement. Group them by subsystem (combustion / lubrication / fuel system / mechanical) to match the health-index structure.
- **Subsystem health strip:** four numbers (0–100) with the same color coding, directly under the parameter bars for that subsystem.
- **Trend chart:** a rolling line chart (last N minutes) for whichever parameter is currently worst-status — this is what makes a developing fault visible as a trend, not just a single bad number.

### 4.3 Past-flight view
- Flight picker (`st.selectbox`) listing `flights` where `status = 'complete'`, showing `flight_id`, zone, and whether a fault was injected.
- Same bar/gauge/health-strip layout as the live view, but driven by a time-scrubber (`st.slider` over `mission_time_s`) instead of polling — lets a judge "rewind" to the exact moment a fault developed.
- Maintenance-advisory panel (separate tab/section): `corrosion_tracking` trend for the simulated airframe across all its flights — this is the one view that's inherently cross-flight rather than single-flight.

### 4.4 Refresh mechanics
Given Streamlit reruns the whole script on each interaction, keep the live-polling loop scoped to a fragment (or `st.empty()` placeholder updated in a loop) rather than the full page, so the flight-picker/tab state doesn't reset every 2–3 seconds while a live flight is being watched.

---

## BUILD ORDER

1. **Schema + File 1 skeleton** — get one complete flight's worth of engine-only telemetry (no environmental fields yet) writing to SQLite with the seeded/reproducible design from §1.3. Verify reproducibility first: run the same `flight_id` twice, diff the output, confirm it's identical.
2. **File 2 skeleton, engine-only** — expected values + debounced status against File 1's output, still no environmental layer. Verify the flicker fix: inject a fault, confirm status changes are stable and not oscillating packet-to-packet.
3. **Environmental fields into File 1** — humidity, pressure altitude, climate zone, filter/maritime hour tracking.
4. **Environmental corrections into File 2** — density altitude, icing risk + fault-attribution override, dust drift, corrosion index (separate table).
5. **Dashboard, live view only** — bars/gauges + health strip + status banner against a currently-running flight.
6. **Dashboard, historical view** — flight picker + scrubber, reusing the same rendering functions from step 5.
7. **Polish** — trend chart, icing advisory chip, maintenance/corrosion panel, color/layout pass.

Steps 1–2 are the ones to get right before building anything else — every later step depends on the seeding and debounce logic actually working, and both are much easier to verify in isolation (diffing two runs, watching one injected fault) than after the dashboard is layered on top.

## OPEN DECISIONS TO CONFIRM BEFORE BUILDING

- **Concurrent-write handling:** File 1 and File 2 running as separate processes against one SQLite file works for a demo but SQLite's write-locking can stall under truly concurrent writes — fine at 2–3 s packet rates, worth flagging if you later push to sub-second ticks (SQLite → PostgreSQL is the same upgrade path the original plan already called out).
- **Airframe identity for cross-flight tracking:** `hours_since_filter_service` and `maritime_hours_cumulative`/corrosion index need a stable identifier across multiple flights (a simulated tail number), separate from `flight_id` — worth deciding that ID scheme before File 1's schema is finalized rather than retrofitting it.
- **Naturally-aspirated branch:** since the O-320 profile exists as a second calibration point, confirm whether the dashboard needs an engine-profile selector too, or whether Rotax 914 stays the only profile actually wired into the live pipeline for this demo.
