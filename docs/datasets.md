# Datasets and Training Data

## Baseline Mission Dataset

The Rotax 914 baseline dataset contains nine stage definitions, target RPM/throttle/AFR, altitude fraction, default duration, environment settings, and sensor fluctuation settings.

## Raw Export Schema

```text
flight_id, packet_index, time_s, stage, rpm, altitude_m, ambient_temp_c,
cht_c, oil_temp_c, oil_pressure_psi, egt_c, fuel_flow_lph, vibration_g,
battery_voltage_v, bus_voltage_v, alternator_output_a
```

Expected values, deviation percentages, and dashboard health labels are not exported.

## Included Data

- `uav_training_50_flights_1000_packets.csv`: 50 flights with 1,000 raw packets each.
- `rotax914_200_cycles.csv`: multi-cycle generated data.

For supervised experiments, preserve the generator configuration and fault windows alongside the raw CSV; do not mix derived dashboard fields into raw model input.
