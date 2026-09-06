from __future__ import annotations

import os
import logging
import threading
import time
from copy import deepcopy

import can

from ingestion.decoder import decode_can_message

LOGGER = logging.getLogger(__name__)


class CANListener:
    def __init__(self, mission_id: str, interface: str = "vcan0", callback=None):
        self.mission_id = mission_id
        self.interface = interface
        self.data_queue = []
        self.running = False
        self._thread = None
        self.callback = callback
        self._snapshot = {}
        self.received_count = 0
        self.snapshot_count = 0

    _REQUIRED_SIGNALS = {
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
    }

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        bus = can.ThreadSafeBus(interface="socketcan", channel=self.interface)
        try:
            while self.running:
                message = bus.recv(timeout=0.5)
                if message is None:
                    continue
                self.received_count += 1
                try:
                    decoded = decode_can_message(message)
                except (KeyError, TypeError, ValueError):
                    continue
                self._snapshot.update(decoded)
                if "mission_phase" in decoded:
                    self._snapshot["phase_id"] = int(decoded["mission_phase"])
                if not self._REQUIRED_SIGNALS.issubset(self._snapshot):
                    continue
                record = deepcopy(self._snapshot)
                record["mission_id"] = self.mission_id
                record["elapsed_s"] = time.time()
                record.setdefault("phase_id", 4)
                self._snapshot.clear()
                self.snapshot_count += 1
                self.data_queue.append(record)
                if self.callback:
                    try:
                        self.callback(record)
                    except Exception:
                        LOGGER.exception("Telemetry callback failed for CAN ID 0x%03X", message.arbitration_id)
        finally:
            bus.shutdown()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def get_latest(self):
        return self.data_queue[-1] if self.data_queue else None

    def missing_signals(self):
        return sorted(self._REQUIRED_SIGNALS.difference(self._snapshot))
