"""Main simulator orchestration.

Integrates the mission controller, environment model, engine physics,
fault management, and sensor measurements into a single pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .mission import MissionController
from .environment import EnvironmentModel, EnvironmentState
from .engine_model import EngineModel
from .faults import FaultManager
from .sensors import SensorModel
from .telemetry import EngineInputs, EngineState, EngineTelemetry


@dataclass
class SimulatorStepResult:
    """The complete output of a simulation step."""
    mission_state: str
    env_state: EnvironmentState
    true_state: EngineState
    measured_state: EngineTelemetry
    target_throttle: float
    target_load: float


class EngineSimulator:
    """Orchestrates the UAV engine digital twin pipeline.

    Pipeline:
    Mission -> Environment -> Engine -> Faults -> Sensors -> Telemetry
    """

    def __init__(
        self,
        mission_profile: Path,
        seed: Optional[int] = None
    ) -> None:
        self.seed = seed if seed is not None else 42

        # 1. Mission Control
        self.mission = MissionController(mission_profile)

        # 2. Environment
        self.environment = EnvironmentModel()

        # 3. Engine Physics
        self.engine = EngineModel()

        # 4. Faults
        self.faults = FaultManager()

        # 5. Sensors
        self.sensors = SensorModel(seed=self.seed)

    def enable_fault(self, name: str, severity: float) -> None:
        self.faults.enable(name, severity)

    def disable_fault(self, name: str) -> None:
        self.faults.disable(name)

    def step(self, dt: float = 0.1) -> SimulatorStepResult:
        """Execute one step of the simulation pipeline.

        Returns:
            SimulatorStepResult containing truth and measured states.
        """
        # A. Mission Controller -> Target Inputs
        mission_targets = self.mission.step(dt)
        state_name = mission_targets["state_name"]
        throttle = mission_targets["throttle"]
        load = mission_targets["engine_load"]
        altitude = mission_targets["altitude_m"]

        # B. Environment Model -> Atmospheric State
        # We use a default surface temp of 15C; could be made configurable.
        env_state = self.environment.get_state(altitude, surface_temp_c=15.0)

        # C. Apply Physics Faults (Degradation)
        # We modify the engine model's internal parameters based on faults.
        physics_mods = self.faults.get_physics_modifiers()

        # D. Engine Model -> Physical Truth
        # Create inputs for the engine physics
        inputs = EngineInputs(
            throttle=throttle,
            altitude_m=altitude,
            ambient_temperature_c=env_state.ambient_temperature_c,
            engine_load=load,
            engine_health=1.0, # Base health, could be integrated from Mission/Faults
            engine_age_hours=0.0,
        )

        # We pass modifiers to the engine model to simulate degradation
        true_state = self.engine.step(inputs, dt=dt, modifiers=physics_mods)

        # E. Sensor Model -> Measured Telemetry
        # First, update sensor configs based on active sensor faults
        for sensor_name in self.sensors.configs:
            mods = self.faults.get_sensor_modifiers(sensor_name)
            self.sensors.update_config(
                sensor_name,
                drift_rate=mods["drift_rate"],
                bias=mods["bias"],
                failure_mode=mods["failure_mode"]
            )

        measured_state = self.sensors.measure(true_state, dt=dt)

        # Inject mission state into measured telemetry for CAN transmission
        # Convert state_name (string) to a numeric ID for CAN
        stage_map = {
            "OFF": 0, "PRE_FLIGHT": 1, "ENGINE_START": 2, "WARMUP": 3,
            "TAXI": 4, "TAKEOFF": 5, "INITIAL_CLIMB": 6, "CLIMB": 7,
            "CRUISE_CLIMB": 8, "CRUISE": 9, "HIGH_ALTITUDE_CRUISE": 10,
            "LOITER": 11, "DESCENT": 12, "APPROACH": 13, "LANDING": 14,
            "COOLDOWN": 15, "SHUTDOWN": 16, "POST_FLIGHT": 17, "MISSION_COMPLETE": 18,
            "THROTTLE_TRANSITION": 99
        }

        measured_state.mission_stage = float(stage_map.get(state_name, 0))
        measured_state.altitude = float(altitude)
        measured_state.throttle = float(throttle * 100) # Convert 0.0-1.0 to 0-100%
        measured_state.load = float(load * 100)       # Convert 0.0-1.0 to 0-100%

        return SimulatorStepResult(
            mission_state=state_name,
            env_state=env_state,
            true_state=true_state,
            measured_state=measured_state,
            target_throttle=throttle,
            target_load=load
        )
