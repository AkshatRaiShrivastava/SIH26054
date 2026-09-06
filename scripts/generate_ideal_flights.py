#!/usr/bin/env python3
"""Create static no-fault flight datasets using the same schema as the live backend."""

from __future__ import annotations

import argparse
import random
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "uav-engine-digital-twin"))
sys.path.insert(0, str(ROOT / "DashboardCode"))

from backend.flight_recorder import FlightRecorder  # noqa: E402
from backend.models import EngineTelemetry  # noqa: E402
from simulator.simulator import EngineSimulator  # noqa: E402


def generate(args: argparse.Namespace) -> tuple[int, int]:
    if args.replace:
        import psycopg
        connection = psycopg.connect(args.database_url)
        try:
            connection.execute("DELETE FROM flights WHERE label = 'ideal_no_fault'")
            connection.commit()
        finally:
            connection.close()

    rng = random.Random(args.seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    total_rows = 0
    for flight_number in range(args.flights):
        recorder = FlightRecorder(args.database_url, interface="simulator", label="ideal_no_fault")
        simulator = EngineSimulator()
        simulator.set_input("throttle", rng.uniform(0.35, 0.85))
        simulator.set_input("engine_load", rng.uniform(0.35, 0.85))
        simulator.set_input("altitude_m", rng.uniform(0, 2500))
        simulator.set_input("ambient_temperature_c", rng.uniform(5, 30))
        simulator.set_input("engine_health", 1.0)
        for sample_index in range(args.steps):
            source = simulator.step(dt=args.sample_period_s)
            timestamp = start + timedelta(seconds=total_rows * args.sample_period_s)
            recorder.record_snapshot(EngineTelemetry(
                timestamp=timestamp.isoformat(), rpm=round(source.rpm), cht=source.cht_c,
                egt=source.egt_c, oil_pressure=source.oil_pressure_kpa,
                oil_temperature=source.oil_temperature_c, fuel_flow=source.fuel_flow_lph,
                vibration=source.vibration_mms, battery_voltage=source.battery_voltage,
                source_interface="simulator", sequence=sample_index + 1,
            ))
            total_rows += 1
        recorder.close()
    return args.flights, total_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ideal no-fault CAN telemetry flights in PostgreSQL.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://uav:uav_password_123@127.0.0.1:5432/uav_telemetry"))
    parser.add_argument("--flights", type=int, default=15)
    parser.add_argument("--steps", type=int, default=600, help="Time-series samples per flight")
    parser.add_argument("--sample-period-s", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=26054)
    parser.add_argument("--replace", action="store_true", help="Delete previous ideal_no_fault flights before generating")
    args = parser.parse_args()
    if args.flights <= 0 or args.steps <= 0 or args.sample_period_s <= 0:
        parser.error("flights, steps, and sample-period-s must be positive")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    flights, rows = generate(arguments)
    print(f"Created PostgreSQL ideal flight data: {flights} ideal no-fault flights, {rows} time-series rows.")
