# Simulator Console

The Simulator Console at `/simulator/` is the test harness for live missions, fault experiments, and raw dataset generation.

## Default Mission

`START_WARMUP`, `GROUND_IDLE_TAXI`, `TAKEOFF`, `CLIMB`, `CRUISE_TRANSIT`, `LOITER_ISR`, `DESCENT`, `APPROACH_LANDING`, and `SHUTDOWN_COOLDOWN` run in order.

RPM starts at zero, ramps during warm-up, reaches 5800 RPM by takeoff completion, and settles near 5500 RPM during climb.

## Environments

Six presets vary ISA temperature offset and cruise altitude: standard, hot (+30 C), and cold (-25 C), each at normal or high cruise altitude.

## Telemetry and Faults

The console shows raw actual values only: CHT, oil temperature/pressure, EGT, fuel flow, vibration, battery voltage, bus voltage, and alternator current. Expected values and deviation percentages are dashboard/backend responsibilities.

Live faults can target CHT, oil temperature, oil pressure, EGT, fuel flow, or vibration. Clear removes the selected fault immediately.

## Training Export

Choose flights, packets per flight, a specific environment, and any number of stage-bounded faults. Every exported flight includes all mission stages. CSVs contain raw telemetry only; expected values and dashboard-derived health states are intentionally omitted.
