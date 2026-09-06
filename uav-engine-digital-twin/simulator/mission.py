"""Mission control and state machine for the engine simulator."""

from __future__ import annotations

import yaml
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


class MissionState(Enum):
    OFF = 0
    PRE_FLIGHT = 1
    ENGINE_START = 2
    WARMUP = 3
    TAXI = 4
    TAKEOFF = 5
    INITIAL_CLIMB = 6
    CLIMB = 7
    CRUISE_CLIMB = 8
    CRUISE = 9
    HIGH_ALTITUDE_CRUISE = 10
    LOITER = 11
    DESCENT = 12
    APPROACH = 13
    LANDING = 14
    COOLDOWN = 15
    SHUTDOWN = 16
    POST_FLIGHT = 17
    MISSION_COMPLETE = 18
    THROTTLE_TRANSITION = 99  # Transient state


@dataclass
class StateConfig:
    name: str
    duration: float
    target_throttle: float
    target_load: float
    target_altitude: float
    next_state: Optional[str]


class MissionController:
    """Manages the UAV mission state machine and provides target inputs.

    Transitions between states based on duration and provides interpolated targets
    to ensure smooth telemetry.
    """

    def __init__(self, profile_path: Path) -> None:
        self.profile = self._load_profile(profile_path)
        self.current_state_name = "OFF"
        self.state_start_time = 0.0
        self.elapsed_time = 0.0

        # For smooth interpolation
        self.prev_throttle = 0.0
        self.prev_load = 0.0
        self.prev_altitude = 0.0

    def _load_profile(self, path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def get_current_state(self) -> MissionState:
        try:
            return MissionState[self.current_state_name]
        except KeyError:
            return MissionState.OFF

    def step(self, dt: float) -> Dict[str, float]:
        """Advance mission clock and update current state targets.

        Returns:
            A dictionary of target inputs: throttle, load, altitude, and current state.
        """
        self.elapsed_time += dt

        states = self.profile.get("states", {})
        state_cfg = states.get(self.current_state_name)

        if not state_cfg:
            self.current_state_name = "OFF"
            state_cfg = states.get("OFF")

        if not state_cfg:
            raise RuntimeError(f"Mission profile missing configuration for {self.current_state_name}")

        time_in_state = self.elapsed_time - self.state_start_time
        if time_in_state >= state_cfg["duration"]:
            next_state = state_cfg.get("next_state")
            if next_state:
                self.prev_throttle = state_cfg["target_throttle"]
                self.prev_load = state_cfg["target_load"]
                self.prev_altitude = state_cfg["target_altitude"]
                self.current_state_name = next_state
                self.state_start_time = self.elapsed_time
                time_in_state = 0.0

        current_cfg = states.get(self.current_state_name, state_cfg)

        # Smooth interpolation: ramp over the first 5 seconds
        ramp_duration = 5.0
        alpha = min(1.0, time_in_state / ramp_duration) if ramp_duration > 0 else 1.0

        throttle = self.prev_throttle + (current_cfg["target_throttle"] - self.prev_throttle) * alpha
        load = self.prev_load + (current_cfg["target_load"] - self.prev_load) * alpha
        altitude = self.prev_altitude + (current_cfg["target_altitude"] - self.prev_altitude) * alpha

        # Determine reported state
        reported_state = self.current_state_name

        # Transient THROTTLE_TRANSITION:
        # If we are in the ramp period and the throttle change is significant (> 20%)
        if alpha < 1.0 and abs(current_cfg["target_throttle"] - self.prev_throttle) > 0.2:
            # Only trigger during certain phases: climb, cruise, loiter, descent
            transient_phases = {"CLIMB", "INITIAL_CLIMB", "CRUISE", "CRUISE_CLIMB", "LOITER", "DESCENT"}
            if self.current_state_name in transient_phases:
                reported_state = "THROTTLE_TRANSITION"

        return {
            "throttle": throttle,
            "engine_load": load,
            "altitude_m": altitude,
            "state_name": reported_state
        }
