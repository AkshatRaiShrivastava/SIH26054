#!/usr/bin/env python3
"""Generate labelled, CAN-shaped UAV telemetry training data in PostgreSQL.

The generator does not require a CAN interface. It runs the same simulator model
used by the CAN producer, then persists its sensor output together with climate
context and known scenario labels. Climate is deliberately stored outside the
CAN sensor payload because a real ECU normally does not publish it on this bus.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parent.parent
SIMULATOR_ROOT = ROOT / "uav-engine-digital-twin"
sys.path.insert(0, str(SIMULATOR_ROOT))

from simulator.simulator import EngineSimulator  # noqa: E402


FAULTS = (
    "injector_degradation",
    "overheating",
    "lubrication_problem",
    "vibration_fault",
    "sensor_drift",
)

# Representative operating envelopes, not an assertion that every point within
# them is safe to fly. Values vary slightly per generated scenario.
CLIMATES = {
    "temperate_standard": {"ambient_temp_c": 15, "humidity_pct": 50, "altitude_m": 500, "wind_mps": 5, "precipitation": "none", "dust_index": 0.1, "salt_exposure": 0.0},
    "hot_desert": {"ambient_temp_c": 42, "humidity_pct": 12, "altitude_m": 800, "wind_mps": 9, "precipitation": "none", "dust_index": 0.9, "salt_exposure": 0.0},
    "humid_monsoon": {"ambient_temp_c": 30, "humidity_pct": 92, "altitude_m": 400, "wind_mps": 14, "precipitation": "heavy_rain", "dust_index": 0.2, "salt_exposure": 0.1},
    "maritime_coastal": {"ambient_temp_c": 27, "humidity_pct": 82, "altitude_m": 150, "wind_mps": 12, "precipitation": "light_rain", "dust_index": 0.1, "salt_exposure": 0.9},
    "cold_high_altitude": {"ambient_temp_c": -12, "humidity_pct": 55, "altitude_m": 4500, "wind_mps": 18, "precipitation": "snow", "dust_index": 0.0, "salt_exposure": 0.0},
    "hot_high_altitude": {"ambient_temp_c": 28, "humidity_pct": 22, "altitude_m": 3500, "wind_mps": 11, "precipitation": "none", "dust_index": 0.5, "salt_exposure": 0.0},
    "tropical_wet": {"ambient_temp_c": 34, "humidity_pct": 88, "altitude_m": 250, "wind_mps": 7, "precipitation": "thunderstorm", "dust_index": 0.1, "salt_exposure": 0.2},
    "cold_dry": {"ambient_temp_c": -25, "humidity_pct": 25, "altitude_m": 1200, "wind_mps": 8, "precipitation": "none", "dust_index": 0.1, "salt_exposure": 0.0},
}


def all_fault_combinations() -> list[tuple[str, ...]]:
    return [combo for size in range(len(FAULTS) + 1) for combo in itertools.combinations(FAULTS, size)]


def create_schema(connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS training_scenarios (
            scenario_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            climate_profile TEXT NOT NULL,
            fault_combination TEXT NOT NULL,
            fault_count INTEGER NOT NULL,
            fault_severity REAL NOT NULL,
            labels_json TEXT NOT NULL,
            ambient_temp_c REAL NOT NULL,
            humidity_pct REAL NOT NULL,
            altitude_m REAL NOT NULL,
            wind_mps REAL NOT NULL,
            precipitation TEXT NOT NULL,
            dust_index REAL NOT NULL,
            salt_exposure REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS training_telemetry (
            scenario_id TEXT NOT NULL REFERENCES training_scenarios(scenario_id),
            sample_index INTEGER NOT NULL,
            timestamp_utc TEXT NOT NULL,
            mission_time_s REAL NOT NULL,
            rpm REAL NOT NULL,
            cht_c REAL NOT NULL,
            egt_c REAL NOT NULL,
            oil_pressure_kpa REAL NOT NULL,
            oil_temperature_c REAL NOT NULL,
            fuel_flow_lph REAL NOT NULL,
            vibration_mms REAL NOT NULL,
            battery_voltage REAL NOT NULL,
            ambient_temp_c REAL NOT NULL,
            humidity_pct REAL NOT NULL,
            altitude_m REAL NOT NULL,
            wind_mps REAL NOT NULL,
            precipitation TEXT NOT NULL,
            dust_index REAL NOT NULL,
            salt_exposure REAL NOT NULL,
            fault_combination TEXT NOT NULL,
            is_faulty INTEGER NOT NULL,
            injector_degradation INTEGER NOT NULL,
            overheating INTEGER NOT NULL,
            lubrication_problem INTEGER NOT NULL,
            vibration_fault INTEGER NOT NULL,
            sensor_drift INTEGER NOT NULL,
            PRIMARY KEY (scenario_id, sample_index)
        );
        CREATE INDEX IF NOT EXISTS idx_training_telemetry_labels ON training_telemetry (fault_combination, scenario_id);
        CREATE INDEX IF NOT EXISTS idx_training_telemetry_climate ON training_telemetry (ambient_temp_c, altitude_m);
        """
    )


def climate_for_scenario(profile: dict[str, float | str], rng: random.Random) -> dict[str, float | str]:
    result = dict(profile)
    result["ambient_temp_c"] = round(float(result["ambient_temp_c"]) + rng.uniform(-3, 3), 2)
    result["humidity_pct"] = round(max(0, min(100, float(result["humidity_pct"]) + rng.uniform(-8, 8))), 2)
    result["altitude_m"] = round(max(0, float(result["altitude_m"]) + rng.uniform(-150, 150)), 1)
    result["wind_mps"] = round(max(0, float(result["wind_mps"]) + rng.uniform(-3, 3)), 2)
    return result


def generate(args: argparse.Namespace) -> tuple[int, int]:
    connection = psycopg.connect(args.database_url)
    if args.replace:
        connection.execute("DROP TABLE IF EXISTS training_telemetry CASCADE")
        connection.execute("DROP TABLE IF EXISTS training_scenarios CASCADE")
        connection.commit()
    create_schema(connection)
    rng = random.Random(args.seed)
    timestamp_origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    scenarios = 0
    rows = 0
    combinations = all_fault_combinations()

    try:
        for climate_name, base_climate in CLIMATES.items():
            for combination in combinations:
                for variant in range(args.samples_per_scenario):
                    scenario_id = f"{climate_name}__{'normal' if not combination else '+'.join(combination)}__{variant:03d}"
                    climate = climate_for_scenario(base_climate, rng)
                    labels = {fault: int(fault in combination) for fault in FAULTS}
                    fault_label = "normal" if not combination else "+".join(combination)
                    connection.execute(
                        """INSERT INTO training_scenarios VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (scenario_id, datetime.now(timezone.utc).isoformat(), climate_name, fault_label, len(combination), args.severity if combination else 0.0, json.dumps(labels, sort_keys=True), climate["ambient_temp_c"], climate["humidity_pct"], climate["altitude_m"], climate["wind_mps"], climate["precipitation"], climate["dust_index"], climate["salt_exposure"]),
                    )
                    simulator = EngineSimulator()
                    simulator.set_input("ambient_temperature_c", float(climate["ambient_temp_c"]))
                    simulator.set_input("altitude_m", float(climate["altitude_m"]))
                    simulator.set_input("throttle", rng.uniform(0.45, 0.9))
                    simulator.set_input("engine_load", rng.uniform(0.4, 0.95))
                    simulator.set_input("engine_age_hours", rng.uniform(0, 2000))
                    for fault in combination:
                        simulator.enable_fault(fault, args.severity)
                    for sample_index in range(args.steps):
                        telemetry = simulator.step(dt=args.sample_period_s)
                        sample_time = timestamp_origin + timedelta(seconds=rows * args.sample_period_s)
                        connection.execute(
                            """INSERT INTO training_telemetry (
                                scenario_id, sample_index, timestamp_utc, mission_time_s,
                                rpm, cht_c, egt_c, oil_pressure_kpa, oil_temperature_c, fuel_flow_lph, vibration_mms, battery_voltage,
                                ambient_temp_c, humidity_pct, altitude_m, wind_mps, precipitation, dust_index, salt_exposure,
                                fault_combination, is_faulty, injector_degradation, overheating, lubrication_problem, vibration_fault, sensor_drift
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (scenario_id, sample_index, sample_time.isoformat(), sample_index * args.sample_period_s,
                             telemetry.rpm, telemetry.cht_c, telemetry.egt_c, telemetry.oil_pressure_kpa, telemetry.oil_temperature_c, telemetry.fuel_flow_lph, telemetry.vibration_mms, telemetry.battery_voltage,
                             climate["ambient_temp_c"], climate["humidity_pct"], climate["altitude_m"], climate["wind_mps"], climate["precipitation"], climate["dust_index"], climate["salt_exposure"],
                             fault_label, int(bool(combination)), labels["injector_degradation"], labels["overheating"], labels["lubrication_problem"], labels["vibration_fault"], labels["sensor_drift"]),
                        )
                        rows += 1
                    scenarios += 1
                    if scenarios % 50 == 0:
                        connection.commit()
        connection.commit()
    finally:
        connection.close()
    return scenarios, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate labelled, climate-aware UAV telemetry into PostgreSQL.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://uav:uav_password_123@127.0.0.1:5432/uav_telemetry"))
    parser.add_argument("--steps", type=int, default=300, help="Time-series records per scenario (default: 300)")
    parser.add_argument("--sample-period-s", type=float, default=0.1)
    parser.add_argument("--samples-per-scenario", type=int, default=3, help="Climate/input variations per climate-fault combination")
    parser.add_argument("--severity", type=float, default=0.7, help="Severity applied to every active fault, 0..1")
    parser.add_argument("--seed", type=int, default=26054)
    parser.add_argument("--replace", action="store_true", help="Replace existing training_* tables")
    args = parser.parse_args()
    if args.steps <= 0 or args.samples_per_scenario <= 0 or args.sample_period_s <= 0:
        parser.error("steps, samples-per-scenario, and sample-period-s must be positive")
    if not 0 <= args.severity <= 1:
        parser.error("severity must be between 0 and 1")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    scenario_count, row_count = generate(arguments)
    print(f"Created PostgreSQL training tables: {scenario_count} labelled scenarios, {row_count} time-series rows.")
