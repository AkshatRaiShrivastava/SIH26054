"""Telemetry data structures."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class EngineInputs:
    throttle: float = 0.5
    altitude_m: float = 0.0
    ambient_temperature_c: float = 15.0
    engine_load: float = 0.5
    engine_age_hours: float = 0.0
    engine_health: float = 1.0


@dataclass
class EngineTelemetry:
    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_lph: float
    vibration_mms: float
    battery_voltage: float

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)
