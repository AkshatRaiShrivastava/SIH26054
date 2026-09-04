"""Main simulator orchestration."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from .engine_model import EngineModel
from .faults import FaultManager
from .telemetry import EngineInputs, EngineTelemetry


@dataclass
class SimulatorState:
    throttle: float = 0.5
    altitude_m: float = 0.0
    ambient_temperature_c: float = 15.0
    engine_load: float = 0.5
    engine_age_hours: float = 0.0
    engine_health: float = 1.0


class EngineSimulator:
    """Produces smooth telemetry from controllable engine inputs."""

    def __init__(self, state: Optional[SimulatorState] = None) -> None:
        self.state = state or SimulatorState()
        self.model = EngineModel()
        self.faults = FaultManager()
        self._rng = random.Random(42)

    def set_input(self, name: str, value: float) -> None:
        if not hasattr(self.state, name):
            raise ValueError(f"Unknown simulator input: {name}")
        setattr(self.state, name, value)

    def enable_fault(self, name: str, severity: float) -> None:
        self.faults.enable(name, severity)

    def disable_fault(self, name: str) -> None:
        self.faults.disable(name)

    def step(self, dt: float = 0.1) -> EngineTelemetry:
        # Small deterministic environment drift keeps the signal smooth.
        jitter_alt = self._rng.uniform(-0.5, 0.5)
        jitter_temp = self._rng.uniform(-0.2, 0.2)
        self.state.altitude_m = max(0.0, self.state.altitude_m + jitter_alt)
        self.state.ambient_temperature_c += jitter_temp * 0.02

        inputs = EngineInputs(
            throttle=self.state.throttle,
            altitude_m=self.state.altitude_m,
            ambient_temperature_c=self.state.ambient_temperature_c,
            engine_load=self.state.engine_load,
            engine_age_hours=self.state.engine_age_hours,
            engine_health=self.state.engine_health,
        )
        telemetry = self.model.step(inputs, dt=dt)
        return self.faults.apply(telemetry, baseline_rpm=max(1200.0, telemetry.rpm))

    def run(self, callback, dt: float = 0.1) -> None:
        while True:
            telemetry = self.step(dt=dt)
            callback(telemetry)
            time.sleep(dt)
