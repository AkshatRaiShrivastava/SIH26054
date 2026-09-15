"""FADEC process: run MissionSimulator and emit encrypted CAN telemetry."""

import argparse
import os
import time
from pathlib import Path

import can

from EngineSimulator.files.mission_simulator import MissionConfig, MissionSimulator
from EngineSimulator.files.mission_stages import load_dataset
from EngineSimulator.files.wire_format import (
    FAULT_CAN_ID, HEARTBEAT_CAN_ID, TELEMETRY_CAN_ID, encrypt_payload,
    fragment, key_from_environment, pack_telemetry,
)


class FadecCanTransmitter:
    def __init__(self, bus: can.BusABC, key: bytes):
        self.bus = bus
        self.key = key

    def _send_encrypted(self, can_id: int, payload: bytes) -> None:
        for data in fragment(encrypt_payload(payload, self.key)):
            self.bus.send(can.Message(arbitration_id=can_id, data=data, is_extended_id=False))

    def send_telemetry(self, row: dict) -> None:
        print(f"FADEC: sending telemetry at time {row.get('time_s', '?')}s, stage {row.get('stage', '?')}")
        self._send_encrypted(TELEMETRY_CAN_ID, pack_telemetry(row))

    def send_heartbeat(self, timestamp_s: float) -> None:
        self._send_encrypted(HEARTBEAT_CAN_ID, str(timestamp_s).encode())

    def send_fault_event(self, event: dict) -> None:
        import json
        self._send_encrypted(FAULT_CAN_ID, json.dumps(event, separators=(",", ":")).encode())


def open_bus() -> can.BusABC:
    backend = os.environ.get("CAN_BACKEND", "virtual")
    if backend == "socketcan":
        return can.Bus(interface="socketcan", channel=os.environ.get("CAN_CHANNEL", "vcan0"), fd=False)
    return can.Bus(interface="virtual", channel=os.environ.get("CAN_CHANNEL", "uav-fadec"), receive_own_messages=False)


def run() -> None:
    parser = argparse.ArgumentParser()
    default_dataset = Path(__file__).resolve().parents[1] / "datasets" / "rotax914_baseline_dataset.json"
    parser.add_argument("--dataset", default=str(default_dataset))
    parser.add_argument("--environment", default="standard_normal_altitude")
    parser.add_argument("--duration", type=float, default=None, help="override every stage duration (if provided)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if args.duration is not None:
        durations = {stage[0]: args.duration for stage in dataset["stages"]}
    else:
        durations = {stage[0]: stage[5] for stage in dataset["stages"]}  # use default_duration_s from stage tuple
    simulator = MissionSimulator(MissionConfig(args.environment, durations, dataset=dataset), seed=args.seed)
    simulator.start_realtime()
    key = key_from_environment()
    bus = open_bus()
    transmitter = FadecCanTransmitter(bus, key)
    last_heartbeat = 0.0
    try:
        while not simulator.realtime_finished:
            row = simulator.step_realtime()
            transmitter.send_telemetry(row)
            if row["time_s"] - last_heartbeat >= 1.0 or last_heartbeat == 0.0:
                transmitter.send_heartbeat(row["time_s"])
                last_heartbeat = row["time_s"]
            time.sleep(simulator.dt)
    finally:
        bus.shutdown()


if __name__ == "__main__":
    run()
