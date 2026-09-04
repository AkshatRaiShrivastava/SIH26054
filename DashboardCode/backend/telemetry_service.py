"""Single-consumer CAN ingestion service."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from .can_decoder import CANDecoder, CANMapping
from .flight_recorder import FlightRecorder
from .telemetry_state import TelemetryState
from .validator import TelemetryValidator


class TelemetryService:
    def __init__(self, interface: str, mapping_path: str | Path, recorder: FlightRecorder | None = None) -> None:
        self.interface = interface
        self.mapping = CANMapping.load(mapping_path)
        self.decoder = CANDecoder(self.mapping)
        self.validator = TelemetryValidator()
        self.state = TelemetryState(interface=interface)
        self.recorder = recorder
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bus = None

    def _ensure_bus(self):
        if self._bus is None:
            import can  # type: ignore

            self._bus = can.Bus(interface="socketcan", channel=self.interface)
        return self._bus

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            bus = self._ensure_bus()
        except Exception:
            # Keep the backend alive even if CAN is temporarily unavailable.
            return

        while not self._stop_event.is_set():
            message = bus.recv(timeout=0.1)
            if message is None:
                continue
            decoded = self.decoder.decode(message)
            if decoded is None:
                self.state.mark_frame(valid=True, known=False)
                continue

            signal_name, value = decoded
            mapping = self.mapping.mappings.get(int(message.arbitration_id))
            if mapping is None:
                self.state.mark_frame(valid=True, known=False)
                continue

            validation = self.validator.validate(mapping, value)
            self.state.mark_frame(valid=validation.valid, known=True)
            if not validation.valid:
                continue

            snapshot = self.state.update({signal_name: validation.value})
            if self.recorder:
                self.recorder.record_signal(signal_name, snapshot)
