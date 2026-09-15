# Build prompt: Rotax 914-class UAV Engine Mission Simulator & Replay System

Paste everything below into a fresh AI coding session (Claude Code or similar) to build this from scratch. It is self-contained — no other document is needed.

---

## Context

We are building the "Simulation & Replay" module of a Digital Twin for a Rotax 914-class piston engine on a MALE (Medium Altitude Long Endurance) UAV. This module generates realistic engine telemetry for demo/testing purposes and lets an operator manually inject faults to prove the downstream anomaly-detection and health-index modules work. It must also store every generated mission and replay it later from storage — not regenerate it.

## Physics model (implement exactly as given — these are not arbitrary)

All expected values are functions of RPM, altitude, and ambient temperature deviation from standard atmosphere. Compute `sigma` (air density ratio) once per timestep and reuse it everywhere.

```
T(h)          = 288.15 - 0.0065*h                        [Kelvin, h in meters]
sigma(h)      = (1 - 2.2558e-5 * h) ** 4.2559             [rho(h)/rho0]
ambient_temp_c(h, isa_dev_c) = (T(h) - 273.15) + isa_dev_c

cht_base(rpm)        = 100 + 90*(rpm/5800)                [placeholder curve, re-fit later]
cht_expected         = cht_base(rpm) + 0.5*(t_amb_c - 15) - 15*(sigma - 1)

oil_temp_expected    = 55 + 0.009*rpm + 0.6*t_amb_c - 8*(sigma - 1)
# oil pressure is a TWO-PIECE function — branch on rpm, do not interpolate across 3500 rpm:
if rpm < 3500:
    oil_pressure_expected = 12.0                           # psi floor
else:
    viscosity_factor = exp(-0.02 * (oil_temp_c - 90))
    oil_pressure_expected = 0.013 * rpm * viscosity_factor

egt_expected = 500 + 0.06*rpm + 40*(afr_actual - 14.7)     # 14.7 = stoichiometric AFR, not tunable

k_power = 58.0 / (5500 * 0.95)      # calibrated once: 58kW at rpm=5500, throttle=0.95 (manual's max-continuous point)
power_estimate_kw   = k_power * rpm * throttle_fraction
fuel_flow_expected_lph = (285 * power_estimate_kw) / 720    # BSFC=285 g/kWh, fuel density=720 g/L

vibration_baseline(rpm):  # no closed-form physics — empirical curve with two resonance bumps
    x = rpm/5800
    base = 0.15 + 0.35*x
    bump1 = 0.12 * exp(-((rpm-3800)/300)**2)
    bump2 = 0.08 * exp(-((rpm-5200)/250)**2)
    return base + bump1 + bump2

deviation_pct(actual, expected) = (actual - expected) / expected * 100
```

## Mission stage sequence (fixed order; durations are operator-configurable)

| Stage | Target RPM | Throttle | AFR | Altitude (0=airfield, 1=cruise) | Default duration |
|---|---|---|---|---|---|
| GROUND_IDLE | 1400 | 0.08 | 14.7 | 0.00 | 120s |
| TAXI | 1800 | 0.15 | 14.7 | 0.00 | 180s |
| TAKEOFF | 5800 | 1.00 | 12.5 | 0.05 | 60s |
| CLIMB | 5200 | 0.85 | 13.5 | 0.55 | 600s |
| CRUISE_LOITER | 4200 | 0.55 | 15.0 | 1.00 | 3600s (endurance stage) |
| DESCENT | 3000 | 0.25 | 14.7 | 0.30 | 480s |
| LANDING | 2500 | 0.20 | 14.7 | 0.05 | 90s |
| SHUTDOWN | 800 | 0.00 | 14.7 | 0.00 | 60s |

Also implement a **Rapid Throttle Transition** scenario: hold a low RPM/throttle for ~15s, then step to a high RPM/throttle within ~3s and hold for ~20s. This tests transient response, not steady-state.

## Environmental presets (operator picks ONE at mission start)

Each preset = `(isa_dev_c, cruise_altitude_m, airfield_elevation_m)`:
- `standard_normal_altitude` = (0, 2500, 300)
- `hot_normal_altitude` = (+30, 2500, 300)
- `cold_normal_altitude` = (-25, 2500, 300)
- `standard_high_altitude` = (0, 6000, 300)
- `hot_high_altitude` = (+30, 6000, 300)
- `cold_high_altitude` = (-25, 6000, 300)

## Requirements checklist (all must hold)

1. **Configurable at mission start**: climatic condition (one of the 6 presets above), and a per-stage duration override (dict, e.g. `{"CRUISE_LOITER": 7200}`).
2. **Coherent states, never random-per-parameter**: when moving from one stage to the next, RPM and altitude must RAMP linearly over ~10-15 seconds toward the new stage's target, not jump instantly. Every channel's "actual" value must be computed FROM the same (rpm, altitude, ambient_temp) at that instant — never generate CHT and EGT from unrelated random draws.
3. **Realistic fluctuation during normal operation**: apply small smoothed noise (AR(1)/exponentially-smoothed random walk, NOT raw white noise) on top of every expected value, roughly ±1-2% for temperatures/pressures, ±3-5% for vibration. Smoothed noise looks like a real sensor; independent-per-tick random noise looks fake.
4. **Runtime-controllable fault injection**: expose `set_fault(channel, percent, ramp_seconds)` and `clear_fault(channel, ramp_seconds)` callable WHILE the simulation is running (not just at config time). `percent` is a signed percentage applied multiplicatively on top of the expected value (e.g. `-25` means the actual reading ramps down to 25% below expected). Support multiple simultaneous faults on different channels.
5. **Endurance/degradation scenario**: a separate `enable_wear(pct_per_hour)` mechanism — a slow, automatic, one-directional drift (not a step fault) applied over long CRUISE_LOITER durations, e.g. oil pressure trending down and vibration/CHT trending up as elapsed mission hours increase. This is distinct from manual fault injection.
6. **Every mission must be stored**, not just streamed: write one file per mission (JSON is fine) containing: mission name, full config (environment + stage durations), the complete timeseries (every timestep, both expected and actual values per channel, per-channel deviation_pct, and which faults were active at that instant), and a chronological event log (stage_start, stage_end, fault_set, fault_cleared, wear_enabled/disabled — each with a timestamp).
7. **Replay reads history — it never recomputes physics.** The replay component loads the stored file and looks up rows by timestamp only.
8. **Replay controls**: `play()`, `pause()`, `set_speed(multiplier)` (e.g. 0.5x/1x/4x/10x), `seek(time_s)`, and an `advance(real_dt_seconds)` method the UI calls once per frame that moves the playhead by `real_dt * speed` and auto-pauses at the end. Also expose the full event log and per-stage start/end boundaries so a UI can render a scrubber timeline with fault markers and stage bands.

## Suggested file layout

```
physics_model.py     # pure functions only, no state, no time — the formulas above
mission_stages.py    # STAGE_DEFINITIONS table + ENVIRONMENT_PRESETS dict
mission_simulator.py # MissionConfig, MissionSimulator (fault injection, wear, ramped stages, save_mission)
replay_engine.py      # MissionReplay (load, play/pause/speed/seek/advance, event timeline)
```

A working reference implementation of all four files already exists — ask for it if you don't already have it, rather than re-deriving the formulas from scratch, since the constants are calibrated against the Rotax 914 operator's manual and re-deriving them independently will silently drift from the source values.

## Acceptance test to run when done

1. Run a full mission on `hot_high_altitude`.
2. Mid-way through `CRUISE_LOITER`, call `set_fault("oil_pressure_psi", -25, ramp_s=10)`, wait, then `clear_fault(...)`.
3. Save the mission, then load it in the replay engine and `seek()` to the middle of the fault window.
4. Confirm: `deviation_pct_oil_pressure_psi` is close to -25% during the fault and close to 0% before/after; every OTHER channel's deviation stays small (±2-3%) throughout — proving the fault is isolated and the rest of the state stays coherent.
5. Confirm stage transitions in the saved timeseries show RPM/altitude ramping smoothly (no instant jumps) between stages.

## Explicit non-goals for this module (state these if asked)

- This module does not run the ML anomaly model or health index — it only produces the (expected, actual) pairs those modules consume.
- Vibration has no closed-form physics backing it (per source material) — it's an empirical placeholder curve, flagged as such, not a manufacturer-verified relationship.
