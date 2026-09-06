"""CLI entry point for the enhanced UAV engine telemetry simulator."""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from can_interface.can_sender import CANMapping, CANSender
from simulator.simulator import EngineSimulator
from utils.logger import build_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enhanced UAV engine telemetry simulator")
    parser.add_argument("--interface", default="vcan0", help="SocketCAN interface name")
    parser.add_argument("--mission", default="surveillance", help="Mission profile name (from config/missions/)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for determinism")
    parser.add_argument("--speed", type=float, default=1.0, help="Simulation speed multiplier (1.0 = realtime)")
    parser.add_argument("--record", type=str, help="Path to CSV file for recording telemetry")
    parser.add_argument(
        "--fault",
        action="append",
        default=[],
        metavar="NAME[:SEVERITY]",
        help="Enable a fault. Repeat for combinations, e.g. --fault cooling_degradation:0.5",
    )
    parser.add_argument("--severity", type=float, default=0.7, help="Default severity for faults")
    parser.add_argument("--mapping", default="config/can_mapping.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = build_logger()

    # 1. Initialize Simulator
    # Make path relative to this script's location
    script_dir = Path(__file__).parent
    mission_path = script_dir / "config" / "missions" / f"{args.mission}.yaml"
    if not mission_path.exists():
        logger.error(f"Mission profile not found: {mission_path}")
        sys.exit(1)

    sim = EngineSimulator(
        mission_profile=mission_path,
        seed=args.seed
    )

    # Apply initial faults
    for fault_spec in args.fault:
        name, separator, raw_severity = fault_spec.partition(":")
        try:
            severity = float(raw_severity) if separator else args.severity
            sim.enable_fault(name, severity)
        except ValueError:
            logger.error(f"Invalid severity for fault {name}")

    # 2. Setup CAN Interface
    mapping = CANMapping.load(Path(args.mapping))
    sender = CANSender(args.interface, mapping)

    # 3. Setup Recording
    csv_file = None
    csv_writer = None
    if args.record:
        csv_file = open(args.record, "w", newline="")
        # Headers for both True and Measured states
        headers = ["timestamp", "state", "altitude", "throttle", "load"]
        # true_...
        true_fields = ["rpm", "cht_c", "egt_c", "oil_pressure_kpa", "oil_temperature_c", "fuel_flow_lph", "vibration_mms", "battery_voltage"]
        headers += [f"true_{f}" for f in true_fields]
        # measured_...
        headers += [f"meas_{f}" for f in true_fields]

        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(headers)

    # 4. Execution Loop
    stop_event = threading.Event()
    def _stop(*_): stop_event.set()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    dt = 0.1  # 10Hz base rate
    sim_time = 0.0

    logger.info(f"Starting mission: {args.mission} at speed {args.speed}x")

    try:
        while not stop_event.is_set():
            loop_start = time.time()

            # Step simulation
            # telemetry contains both true_state and measured_state
            results = sim.step(dt=dt)

            # Send measured state over CAN
            sender.send(results.measured_state)

            # Record to CSV
            if csv_writer:
                row = [
                    sim_time,
                    results.mission_state,
                    results.env_state.altitude_m,
                    results.target_throttle,
                    results.target_load
                ]
                # True state values
                true_vals = results.true_state.as_dict().values()
                # Measured state values
                meas_vals = results.measured_state.as_dict().values()
                csv_writer.writerow(row + list(true_vals) + list(meas_vals))

            # Log progress every second
            if int(sim_time * 10) % 10 == 0:
                logger.info(
                    "TIME: %.1fs | STATE: %-15s | ALT: %.0fm | RPM: %.0f | CHT: %.1fC | EGT: %.1fC",
                    sim_time,
                    results.mission_state,
                    results.env_state.altitude_m,
                    results.measured_state.rpm,
                    results.measured_state.cht_c,
                    results.measured_state.egt_c
                )

            sim_time += dt

            # Handle simulation speed
            # Real-time sleep: dt / speed
            sleep_time = (dt / args.speed) - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        sender.close()
        if csv_file:
            csv_file.close()
        logger.info(f"Simulation ended. Total sim time: {sim_time:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
