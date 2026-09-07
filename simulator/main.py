from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from contextlib import suppress

import can

from simulator.checklist import build_checklist_bitmask
from simulator.fault_injection import build_fault_context, fault_severity_for
from simulator.mission_profile import DEFAULT_PHASE_DURATIONS_S, SCENARIO_SPECS, elapsed_to_progress, phase_for_elapsed
from simulator.signal_model import simulate_tick


SIMULATOR_STATE = {
    "running": False,
    "mission_id": None,
    "elapsed_s": 0.0,
    "scenario": "normal",
    "speed_multiplier": 1.0,
    "checklist_mask": 0,
    "previous": {},
    "thread": None,
    "stop_event": threading.Event(),
    "fault_context": {},
}
RUNTIME_DIR = os.getenv("RUNTIME_DIR", "/workspace/runtime")
SCENARIO_FILE = os.path.join(RUNTIME_DIR, "scenario.json")
STATUS_FILE = os.path.join(RUNTIME_DIR, "simulation_status.json")


def write_simulation_status(status: str, mission_id: str, elapsed_s: float, phase_id: int, phase_durations_s: dict[int, float] | None = None) -> None:
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    data = {"status": status, "mission_id": mission_id, "elapsed_s": elapsed_s, "phase_id": phase_id}
    if phase_durations_s:
        data["phase_durations_s"] = phase_durations_s
    with open(STATUS_FILE, "w", encoding="utf-8") as status_file:
        json.dump(data, status_file)


def active_scenario(default: str) -> str:
    try:
        with open(SCENARIO_FILE, encoding="utf-8") as scenario_file:
            scenario = json.load(scenario_file).get("scenario", default)
            return scenario if scenario in SCENARIO_SPECS else default
    except (OSError, json.JSONDecodeError):
        return default


def active_phase_durations() -> dict[int, float]:
    try:
        with open(SCENARIO_FILE, encoding="utf-8") as scenario_file:
            configured = json.load(scenario_file).get("phase_durations_s", {})
            return DEFAULT_PHASE_DURATIONS_S | {int(key): max(1.0, float(value)) for key, value in configured.items()}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return DEFAULT_PHASE_DURATIONS_S


def active_control(default_scenario: str) -> tuple[str, dict[int, float], str | None]:
    try:
        with open(SCENARIO_FILE, encoding="utf-8") as scenario_file:
            control = json.load(scenario_file)
            scenario = control.get("scenario", default_scenario)
            scenario = scenario if scenario in SCENARIO_SPECS else default_scenario
            durations = DEFAULT_PHASE_DURATIONS_S | {int(key): max(1.0, float(value)) for key, value in control.get("phase_durations_s", {}).items()}
            return scenario, durations, control.get("mission_id")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default_scenario, DEFAULT_PHASE_DURATIONS_S, None


def build_can_frame(arbitration_id: int, values: dict):
    payload = b""
    for key in [
        "rpm",
        "cht_c",
        "egt_c",
        "oil_pressure_kpa",
        "oil_temperature_c",
        "fuel_flow_lph",
        "vibration_mms",
        "afr",
        "battery_voltage",
        "altitude_m",
        "ambient_temp_c",
    ]:
        if key in values:
            value = values[key]
            if isinstance(value, int):
                value = float(value)
            payload += int(value).to_bytes(2, byteorder="little", signed=False)
    return can.Message(arbitration_id=arbitration_id, data=payload[:8].ljust(8, b"\x00"), is_extended_id=False)


def encode_uav_payload(data: dict):
    frames = []
    frame_map = [
        (0x100, {"rpm": int(data["rpm"])}),
        (0x101, {"cht_c": int(data["cht_c"])}),
        (0x102, {"egt_c": int(data["egt_c"])}),
        (0x103, {"oil_pressure_kpa": int(data["oil_pressure_kpa"])}),
        (0x104, {"oil_temperature_c": int(data["oil_temperature_c"])}),
        (0x105, {"fuel_flow_lph": int(data["fuel_flow_lph"])}),
        (0x106, {"vibration_mms": int(data["vibration_mms"] * 100)}),
        (0x107, {"afr": int(data["afr"] * 100)}),
        (0x108, {"battery_voltage": int(data["battery_voltage"] * 100)}),
        (0x10B, {"altitude_m": int(data["altitude_m"])}),
        (0x10C, {"ambient_temp_c": int(data["ambient_temp_c"])}),
        (0x109, {"mission_phase": int(data.get("phase_id", 0))}),
    ]
    for arb, payload in frame_map:
        try:
            frames.append(can.Message(arbitration_id=arb, data=payload_to_bytes(payload), is_extended_id=False))
        except Exception:
            pass
    return frames


def payload_to_bytes(payload: dict):
    out = bytearray()
    for _, value in payload.items():
        raw = int(round(float(value)))
        out.extend(raw.to_bytes(2, byteorder="little", signed=False))
    return bytes(out[:8]).ljust(8, b"\x00")


def run_simulation(args: argparse.Namespace):
    bus = can.ThreadSafeBus(interface="socketcan", channel=args.interface)
    try:
        SIMULATOR_STATE["running"] = True
        SIMULATOR_STATE["scenario"] = args.scenario
        SIMULATOR_STATE["speed_multiplier"] = args.speed_multiplier
        SIMULATOR_STATE["fault_context"] = build_fault_context(0, args.scenario)
        SIMULATOR_STATE["mission_id"] = f"MISSION-{int(time.time())}"
        SIMULATOR_STATE["previous"] = {}
        SIMULATOR_STATE["elapsed_s"] = 0.0
        mission_started_monotonic = time.monotonic()
        last_control = None
        write_simulation_status("running", SIMULATOR_STATE["mission_id"], 0.0, 0, active_phase_durations())
        SIMULATOR_STATE["checklist_mask"] = build_checklist_bitmask({
            "oil_pressure_temp": True,
            "fuel_flow": True,
            "rpm_stability": True,
            "battery_alternator": True,
            "vibration": True,
            "can_communication": True,
            "ecu_fadec_handshake": True,
            "injection_timing": True,
        })

        while not SIMULATOR_STATE["stop_event"].is_set():
            elapsed = time.monotonic() - mission_started_monotonic
            scenario, phase_durations_s, configured_mission_id = active_control(args.scenario)
            if configured_mission_id:
                SIMULATOR_STATE["mission_id"] = configured_mission_id
            total_duration_s = sum(phase_durations_s.values())
            if elapsed >= total_duration_s:
                SIMULATOR_STATE["elapsed_s"] = total_duration_s
                write_simulation_status("completed", SIMULATOR_STATE["mission_id"], total_duration_s, 6, phase_durations_s)
                while not SIMULATOR_STATE["stop_event"].is_set():
                    time.sleep(0.25)
                    new_scenario, new_durations, new_mission_id = active_control(args.scenario)
                    if new_mission_id and new_mission_id != SIMULATOR_STATE["mission_id"]:
                        SIMULATOR_STATE["mission_id"] = new_mission_id
                        SIMULATOR_STATE["scenario"] = new_scenario
                        SIMULATOR_STATE["previous"] = {}
                        SIMULATOR_STATE["elapsed_s"] = 0.0
                        mission_started_monotonic = time.monotonic()
                        last_control = None
                        write_simulation_status("running", new_mission_id, 0.0, 0, new_durations)
                        break
                continue
            control = (SIMULATOR_STATE["mission_id"], scenario, tuple(sorted(phase_durations_s.items())))
            if control != last_control:
                mission_started_monotonic = time.monotonic()
                elapsed = 0.0
                SIMULATOR_STATE["elapsed_s"] = 0.0
                SIMULATOR_STATE["previous"] = {}
                last_control = control
            SIMULATOR_STATE["scenario"] = scenario
            severity = fault_severity_for(int(elapsed), scenario)
            SIMULATOR_STATE["fault_context"] = build_fault_context(int(elapsed), scenario)
            tick = simulate_tick(elapsed, SIMULATOR_STATE["previous"], scenario, 100.0 - min(40.0, elapsed / 60.0), severity, phase_durations_s)
            tick["mission_id"] = SIMULATOR_STATE["mission_id"]
            tick["phase_id"] = phase_for_elapsed(elapsed, phase_durations_s)
            write_simulation_status("running", SIMULATOR_STATE["mission_id"], elapsed, tick["phase_id"], phase_durations_s)
            tick["progress_pct"] = elapsed_to_progress(elapsed)
            tick["scenario"] = scenario
            for frame in encode_uav_payload(tick):
                bus.send(frame)
            SIMULATOR_STATE["previous"] = tick
            SIMULATOR_STATE["elapsed_s"] = elapsed
            time.sleep(max(0.05, 1.0 / max(1.0, args.tick_hz)))

        SIMULATOR_STATE["running"] = False
        if SIMULATOR_STATE["elapsed_s"] >= sum(active_phase_durations().values()):
            write_simulation_status("completed", SIMULATOR_STATE["mission_id"], SIMULATOR_STATE["elapsed_s"], 6, active_phase_durations())
    finally:
        bus.shutdown()
        SIMULATOR_STATE["stop_event"].clear()


def parse_args():
    parser = argparse.ArgumentParser(description="Synthetic UAV engine simulator")
    parser.add_argument("--scenario", default="normal", choices=list(SCENARIO_SPECS.keys()))
    parser.add_argument("--speed-multiplier", type=float, default=1.0)
    parser.add_argument("--tick-hz", type=float, default=1.0)
    parser.add_argument("--interface", default=os.getenv("CAN_INTERFACE", "vcan0"))
    return parser.parse_args()


def main():
    args = parse_args()
    stop_event = SIMULATOR_STATE["stop_event"]
    stop_event.clear()

    def handle_signal(signum, frame):
        SIMULATOR_STATE["running"] = False
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    run_simulation(args)


if __name__ == "__main__":
    main()
