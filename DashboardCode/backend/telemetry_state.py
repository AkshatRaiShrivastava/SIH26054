"""Shared telemetry state for API and websocket clients."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from .models import DataHealth, EngineTelemetry, SignalFreshness


SIGNAL_NAMES = [
    "rpm",
    "cht",
    "egt",
    "oil_pressure",
    "oil_temperature",
    "fuel_flow",
    "vibration",
    "battery_voltage",
]


@dataclass
class TelemetryState:
    interface: str
    freshness_window_s: float = 1.5
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _latest: Optional[EngineTelemetry] = field(default=None, init=False)
    _signal_last_seen: Dict[str, datetime] = field(default_factory=dict, init=False)
    _latest_values: Dict[str, float] = field(default_factory=lambda: {
        "rpm": 0.0,
        "cht": 0.0,
        "egt": 0.0,
        "oil_pressure": 0.0,
        "oil_temperature": 0.0,
        "fuel_flow": 0.0,
        "vibration": 0.0,
        "battery_voltage": 0.0,
    }, init=False)
    _frames_received: int = field(default=0, init=False)
    _unknown_frames: int = field(default=0, init=False)
    _invalid_frames: int = field(default=0, init=False)
    _frame_times: deque = field(default_factory=lambda: deque(maxlen=2000), init=False)
    _sequence: int = field(default=0, init=False)

    def mark_frame(self, valid: bool = True, known: bool = True) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._frames_received += 1
            if not known:
                self._unknown_frames += 1
            if not valid:
                self._invalid_frames += 1
            self._frame_times.append(now)

    def update(self, telemetry: Dict[str, float]) -> EngineTelemetry:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._latest_values.update(telemetry)
            self._sequence += 1
            self._latest = EngineTelemetry(
                timestamp=now.isoformat(),
                rpm=int(round(self._latest_values["rpm"])),
                cht=float(self._latest_values["cht"]),
                egt=float(self._latest_values["egt"]),
                oil_pressure=float(self._latest_values["oil_pressure"]),
                oil_temperature=float(self._latest_values["oil_temperature"]),
                fuel_flow=float(self._latest_values["fuel_flow"]),
                vibration=float(self._latest_values["vibration"]),
                battery_voltage=float(self._latest_values["battery_voltage"]),
                source_interface=self.interface,
                sequence=self._sequence,
            )
            for name in telemetry:
                self._signal_last_seen[name] = now
            return self._latest

    def snapshot(self) -> Optional[EngineTelemetry]:
        with self._lock:
            return self._latest.model_copy(deep=True) if self._latest else None

    def health(self) -> DataHealth:
        now = datetime.now(timezone.utc)
        with self._lock:
            while self._frame_times and (now - self._frame_times[0]).total_seconds() > 1.0:
                self._frame_times.popleft()
            frame_rate = len(self._frame_times) / 1.0

            freshness: Dict[str, SignalFreshness] = {}
            fresh_count = 0
            for name in SIGNAL_NAMES:
                last_seen = self._signal_last_seen.get(name)
                if last_seen is None:
                    freshness[name] = SignalFreshness(fresh=False, age_ms=999999, last_seen=None)
                    continue
                age_ms = int((now - last_seen).total_seconds() * 1000)
                is_fresh = age_ms <= int(self.freshness_window_s * 1000)
                if is_fresh:
                    fresh_count += 1
                freshness[name] = SignalFreshness(
                    fresh=is_fresh,
                    age_ms=age_ms,
                    last_seen=last_seen.isoformat(),
                )

            return DataHealth(
                can_interface="CONNECTED" if self._frames_received > 0 else "DISCONNECTED",
                frames_received=self._frames_received,
                frames_per_sec=round(frame_rate, 1),
                unknown_frames=self._unknown_frames,
                invalid_frames=self._invalid_frames,
                signals_total=len(SIGNAL_NAMES),
                signals_fresh=fresh_count,
                signal_freshness=freshness,
                last_update=self._latest.timestamp if self._latest else None,
                latest_sequence=self._sequence,
            )
