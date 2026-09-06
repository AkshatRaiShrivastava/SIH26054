"""Sensor model for simulating measurement effects.

Separates 'Physical Truth' from 'Measured Telemetry' by applying noise,
drift, bias, and failure modes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Optional

from .telemetry import EngineState, EngineTelemetry


@dataclass
class SensorConfig:
    """Configuration for a single sensor's measurement characteristics."""
    noise_std: float = 0.01
    bias: float = 0.0
    drift_rate: float = 0.0
    failure_mode: Optional[str] = None  # 'frozen', 'clipped', 'dead'


class SensorModel:
    """Transforms True Engine State into Measured Telemetry.

    This layer allows for simulating sensor-specific faults independently
    of the actual engine physics.
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

        # Default configurations for each telemetry parameter
        self.configs: Dict[str, SensorConfig] = {
            "rpm": SensorConfig(noise_std=5.0),
            "cht_c": SensorConfig(noise_std=0.2),
            "egt_c": SensorConfig(noise_std=0.5),
            "oil_pressure_kpa": SensorConfig(noise_std=0.1),
            "oil_temperature_c": SensorConfig(noise_std=0.1),
            "fuel_flow_lph": SensorConfig(noise_std=0.02),
            "vibration_mms": SensorConfig(noise_std=0.01),
            "battery_voltage": SensorConfig(noise_std=0.01),
        }

        # Track current drift for each sensor
        self.current_drifts: Dict[str, float] = {name: 0.0 for name in self.configs}

    def update_config(self, name: str, **kwargs) -> None:
        """Update sensor configuration (e.g., to inject drift or bias)."""
        if name not in self.configs:
            raise ValueError(f"Unknown sensor: {name}")

        config = self.configs[name]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

    def measure(self, state: EngineState, dt: float = 0.1) -> EngineTelemetry:
        """Apply measurement effects to the true engine state.

        Args:
            state: The physical truth of the engine.
            dt: Time step for drift accumulation.

        Returns:
            EngineTelemetry containing the measured values.
        """
        measured_values = {}

        # Map EngineState fields to sensor names
        fields = [
            "rpm", "cht_c", "egt_c", "oil_pressure_kpa",
            "oil_temperature_c", "fuel_flow_lph", "vibration_mms", "battery_voltage"
        ]

        for field in fields:
            true_val = getattr(state, field)
            config = self.configs[field]

            # 1. Update Drift
            self.current_drifts[field] += config.drift_rate * dt

            # 2. Apply Bias and Drift
            measured_val = true_val + config.bias + self.current_drifts[field]

            # 3. Apply Gaussian Noise
            # Noise is relative to the value if noise_std is small, or absolute
            noise = self._rng.gauss(0, config.noise_std)
            measured_val += noise

            # 4. Apply Failure Modes
            if config.failure_mode == "dead":
                measured_val = 0.0
            elif config.failure_mode == "frozen":
                # For frozen, we'd need to store the last value.
                # Simplifying for now by keeping it at true_val if no update happens.
                pass
            elif config.failure_mode == "clipped":
                measured_val = max(0.0, min(1000.0, measured_val)) # Generic clip

            measured_values[field] = measured_val

        return EngineTelemetry(**measured_values)
