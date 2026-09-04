"""CLI entry point for the engine telemetry simulator."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from can_interface.can_sender import CANMapping, CANSender
from simulator.simulator import EngineSimulator
from utils.logger import build_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UAV engine telemetry simulator")
    parser.add_argument("--interface", default="vcan0", help="SocketCAN interface name")
    parser.add_argument("--throttle", type=float, default=0.5)
    parser.add_argument("--altitude", type=float, default=0.0)
    parser.add_argument("--ambient-temp", type=float, default=15.0)
    parser.add_argument("--load", type=float, default=0.5)
    parser.add_argument("--age-hours", type=float, default=0.0)
    parser.add_argument("--health", type=float, default=1.0)
    parser.add_argument(
        "--fault",
        action="append",
        default=[],
        metavar="NAME[:SEVERITY]",
        help="Enable a fault. Repeat for combinations, e.g. --fault overheating:1 --fault vibration_fault:0.8",
    )
    parser.add_argument("--severity", type=float, default=0.7, help="Default severity for faults without :SEVERITY")
    parser.add_argument("--mapping", default="config/can_mapping.yaml")
    return parser.parse_args()


def command_loop(sim: EngineSimulator) -> None:
    while True:
        try:
            line = input().strip()
        except EOFError:
            return
        if not line:
            continue
        if line in {"quit", "exit"}:
            raise KeyboardInterrupt
        if line == "status":
            print(f"Inputs: {sim.state}")
            print("Active faults:", ", ".join(f"{fault.name}:{fault.severity:.2f}" for fault in sim.faults.active_faults()) or "none")
            continue
        if line == "faults":
            print("Available faults:", ", ".join(sim.faults.faults))
            print("Active faults:", ", ".join(f"{fault.name}:{fault.severity:.2f}" for fault in sim.faults.active_faults()) or "none")
            continue
        parts = line.split()
        try:
            if len(parts) == 2 and parts[0] in {"throttle", "altitude", "ambient_temp", "load", "health", "age_hours"}:
                field = {
                    "ambient_temp": "ambient_temperature_c", "load": "engine_load", "health": "engine_health",
                    "age_hours": "engine_age_hours", "throttle": "throttle", "altitude": "altitude_m",
                }[parts[0]]
                sim.set_input(field, float(parts[1]))
                print(f"Updated {parts[0]} to {parts[1]}")
                continue
            if len(parts) == 3 and parts[0] == "fault" and parts[1] != "off":
                sim.enable_fault(parts[1], float(parts[2]))
                print(f"Enabled {parts[1]} at severity {float(parts[2]):.2f}")
                continue
            if len(parts) == 3 and parts[0] == "fault" and parts[1] == "off":
                sim.disable_fault(parts[2])
                print(f"Disabled {parts[2]}")
                continue
        except (ValueError, KeyError) as error:
            print(f"Command rejected: {error}")
            continue
        print("Commands: throttle <v>, altitude <m>, ambient_temp <c>, load <v>, health <v>, age_hours <v>, fault <name> <0..1>, fault off <name>, faults, status, quit")


def main() -> int:
    args = parse_args()
    logger = build_logger()

    sim = EngineSimulator()
    sim.set_input("throttle", args.throttle)
    sim.set_input("altitude_m", args.altitude)
    sim.set_input("ambient_temperature_c", args.ambient_temp)
    sim.set_input("engine_load", args.load)
    sim.set_input("engine_age_hours", args.age_hours)
    sim.set_input("engine_health", args.health)

    for fault_spec in args.fault:
        name, separator, raw_severity = fault_spec.partition(":")
        try:
            severity = float(raw_severity) if separator else args.severity
            sim.enable_fault(name, severity)
        except ValueError as error:
            parser.error(str(error))

    mapping = CANMapping.load(Path(args.mapping))
    sender = CANSender(args.interface, mapping)

    stop_event = threading.Event()

    def _stop(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    thread = threading.Thread(target=command_loop, args=(sim,), daemon=True)
    thread.start()

    step = 0
    try:
        while not stop_event.is_set():
            telemetry = sim.step(dt=0.1)
            sender.send(telemetry)
            step += 1
            if step % 10 == 0:
                logger.info(
                    "RPM=%.0f | CHT=%.1f C | EGT=%.1f C | OilP=%.1f kPa | OilT=%.1f C | Fuel=%.2f L/h | Vib=%.2f mm/s | Batt=%.2f V",
                    telemetry.rpm,
                    telemetry.cht_c,
                    telemetry.egt_c,
                    telemetry.oil_pressure_kpa,
                    telemetry.oil_temperature_c,
                    telemetry.fuel_flow_lph,
                    telemetry.vibration_mms,
                    telemetry.battery_voltage,
                )
    finally:
        sender.close()
        logger.info("Simulator stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
