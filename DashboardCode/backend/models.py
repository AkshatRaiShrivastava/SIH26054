"""Backend telemetry models and health state."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EngineTelemetry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rpm: int
    cht: float
    egt: float
    oil_pressure: float
    oil_temperature: float
    fuel_flow: float
    vibration: float
    battery_voltage: float
    mission_stage: float = 0.0
    altitude: float = 0.0
    throttle: float = 0.0
    load: float = 0.0
    source_interface: str = "vcan0"
    sequence: int = 0


class SignalFreshness(BaseModel):
    fresh: bool
    age_ms: int
    last_seen: Optional[str] = None


class DataHealth(BaseModel):
    can_interface: Literal["CONNECTED", "DISCONNECTED"] = "DISCONNECTED"
    frames_received: int = 0
    total_frames: int = 0
    frames_per_sec: float = 0.0
    unknown_frames: int = 0
    invalid_frames: int = 0
    signals_total: int = 12
    signals_fresh: int = 0
    stale: bool = False
    signal_freshness: Dict[str, SignalFreshness] = Field(default_factory=dict)
    last_update: Optional[str] = None
    latest_sequence: int = 0


class HealthSnapshot(BaseModel):
    ok: bool = True
    can_interface: str = "DISCONNECTED"
    backend: str = "running"
    message: str = "Telemetry backend is ready"


class TelemetryMessage(BaseModel):
    timestamp: str
    rpm: int
    cht: float
    egt: float
    oil_pressure: float
    oil_temperature: float
    fuel_flow: float
    vibration: float
    battery_voltage: float
    mission_stage: float = 0.0
    altitude: float = 0.0
    throttle: float = 0.0
    load: float = 0.0
    source_interface: str
    sequence: int
