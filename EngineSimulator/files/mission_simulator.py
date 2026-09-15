"""
mission_simulator.py
=====================
Runs one full mission: a fixed stage sequence, with operator-configured
climatic condition, cruise altitude, and per-stage duration. Produces a
COHERENT telemetry stream (RPM/altitude ramp smoothly between stages, not
random per-parameter jumps), with small realistic fluctuation layered on
top of the physics-informed expected values, and full runtime control over
fault injection.

Design contract (matches the requirement table):
  - Environmental condition simulation -> MissionConfig(environment=...)
  - High altitude / Hot weather        -> just an environment preset choice
  - Endurance mission with degradation -> enable_wear() during CRUISE_LOITER
  - Rapid throttle transitions         -> RapidThrottleScenario (below)
  - Coherent states, not random values -> ramped stage transitions + AR(1) noise
  - Controllable fault injection       -> set_fault()/clear_fault(), live, mid-run
  - Missions stored & replayable       -> save_mission() writes one JSON file
"""

import json
import random
import time as time_module

import EngineSimulator.files.physics_model as pm
from EngineSimulator.files.mission_stages import DEFAULT_DATASET, stage_altitude_m


# Per-channel fluctuation size (fraction of expected value, 1-sigma) and
# smoothing (higher = smoother/slower-moving noise, 0-1).
FLUCTUATION = {
    "cht_c":           (0.015, 0.90),
    "oil_temp_c":      (0.012, 0.92),
    "oil_pressure_psi":(0.02,  0.85),
    "egt_c":           (0.015, 0.88),
    "fuel_flow_lph":   (0.03,  0.80),
    "vibration_g":     (0.05,  0.70),
}

RAMP_TIME_S = 12.0   # time to blend RPM/altitude from previous stage into this one


class _NoiseChannel:
    """AR(1)-style smoothed noise so fluctuation looks like a real sensor, not white noise."""

    def __init__(self, sigma_frac: float, smoothing: float):
        self.sigma_frac = sigma_frac
        self.smoothing = smoothing
        self.value = 0.0

    def next(self) -> float:
        self.value = self.smoothing * self.value + (1 - self.smoothing) * random.gauss(0, self.sigma_frac)
        return self.value


class FaultState:
    """One active (or ramping-out) fault on a single channel."""

    def __init__(self, channel: str, target_pct: float, ramp_s: float):
        self.channel = channel
        self.target_pct = target_pct
        self.current_pct = 0.0
        self.ramp_s = max(ramp_s, 0.1)

    def step(self, dt: float):
        step_frac = dt / self.ramp_s
        self.current_pct += (self.target_pct - self.current_pct) * min(1.0, step_frac)


class MissionConfig:
    def __init__(self, environment: str, stage_durations_s: dict = None, dataset: dict = None):
        self.dataset = dataset or DEFAULT_DATASET
        environments = self.dataset["environments"]
        if environment not in environments:
            raise ValueError(f"Unknown environment '{environment}'. Options: {list(environments)}")
        self.environment = environment
        self.isa_dev_c, self.cruise_altitude_m, self.airfield_elevation_m, self.label = environments[environment]
        # Operator can override any stage's duration; unspecified stages use the default.
        self.stage_durations_s = dict(stage_durations_s or {})

    def duration_for(self, stage_name: str, default_s: float) -> float:
        return self.stage_durations_s.get(stage_name, default_s)


class MissionSimulator:
    def __init__(self, config: MissionConfig, dt_s: float = 1.0, seed: int = None):
        self.config = config
        self.dataset = config.dataset
        self.stage_definitions = self.dataset["stages"]
        self.fluctuation = self.dataset["fluctuation"]
        self.dt = dt_s
        if seed is not None:
            random.seed(seed)

        self.noise = {ch: _NoiseChannel(s, k) for ch, (s, k) in self.fluctuation.items()}
        self.active_faults = {}       # channel -> FaultState
        self.wear_enabled = False
        self.wear_pct_per_hour = 0.0
        self.wear_elapsed_s = 0.0

        self.time_s = 0.0
        self.timeseries = []
        self.events = []

        self._prev_rpm = self.stage_definitions[0][1]
        self._prev_altitude_m = stage_altitude_m(self.stage_definitions[0][4],
                                                  self.config.airfield_elevation_m,
                                                  self.config.cruise_altitude_m)
        self._realtime_stage_index = 0
        self._realtime_stage_elapsed_s = 0.0
        self._realtime_started = False
        self._realtime_finished = False

    # ------------------------------------------------------------------
    # Convenience API: endurance / degradation scenario
    # ------------------------------------------------------------------
    def run_endurance_mission(self, wear_pct_per_hour: float = 1.0):
        """Run a full mission with endurance wear enabled.

        This helper enables the wear drift (degradation) for the entire
        mission, then executes the normal stage sequence. The caller can
        adjust the wear rate via ``wear_pct_per_hour`` – the percentage
        drift applied to each channel per simulated hour.
        """
        # Enable wear before any stage runs so the loiter stage experiences
        # the gradual degradation required by the endurance requirement.
        self.enable_wear(pct_per_hour=wear_pct_per_hour)
        self.run_full_mission()

    # ------------------------------------------------------------------
    # Fault injection API -- callable at any point while the sim is running
    # ------------------------------------------------------------------
    def set_fault(self, channel: str, percent: float, ramp_s: float = 5.0):
        """percent: +N% increases the actual value above expected, -N% decreases it."""
        if channel not in self.fluctuation:
            raise ValueError(f"Unknown channel '{channel}'. Options: {list(self.fluctuation)}")
        self.active_faults[channel] = FaultState(channel, percent, ramp_s)
        self.events.append({"time_s": self.time_s, "type": "fault_set",
                             "channel": channel, "target_pct": percent, "ramp_s": ramp_s})

    def clear_fault(self, channel: str, ramp_s: float = 5.0):
        if channel in self.active_faults:
            self.active_faults[channel].target_pct = 0.0
            self.active_faults[channel].ramp_s = ramp_s
            self.events.append({"time_s": self.time_s, "type": "fault_cleared", "channel": channel})

    def enable_wear(self, pct_per_hour: float = 1.0):
        """Slow, automatic one-directional drift for the endurance/degradation scenario."""
        self.wear_enabled = True
        self.wear_pct_per_hour = pct_per_hour
        self.events.append({"time_s": self.time_s, "type": "wear_enabled", "pct_per_hour": pct_per_hour})

    def disable_wear(self):
        self.wear_enabled = False
        self.events.append({"time_s": self.time_s, "type": "wear_disabled"})

    def start_realtime(self):
        """Prepare the simulator for one-second-at-a-time interactive stepping."""
        self._realtime_stage_index = 0
        self._realtime_stage_elapsed_s = 0.0
        self._realtime_started = True
        self._realtime_finished = False
        self.events.append({"time_s": self.time_s, "type": "mission_start"})

    @property
    def realtime_finished(self):
        return self._realtime_finished

    @property
    def realtime_stage(self):
        if self._realtime_finished:
            return self.stage_definitions[-1][0]
        return self.stage_definitions[self._realtime_stage_index][0]

    def step_realtime(self):
        """Generate exactly one timestep and advance the active mission stage."""
        if not self._realtime_started:
            self.start_realtime()
        if self._realtime_finished:
            return self.timeseries[-1] if self.timeseries else None

        name, target_rpm, throttle, afr, alt_frac, default_duration = self.stage_definitions[self._realtime_stage_index]
        duration_s = self.config.duration_for(name, default_duration)
        if self._realtime_stage_elapsed_s == 0.0:
            self.events.append({"time_s": self.time_s, "type": "stage_start", "stage": name})

        target_altitude = stage_altitude_m(alt_frac, self.config.airfield_elevation_m,
                                          self.config.cruise_altitude_m)
        ramp_frac = min(1.0, self._realtime_stage_elapsed_s / RAMP_TIME_S)
        rpm = self._prev_rpm + (target_rpm - self._prev_rpm) * ramp_frac
        altitude_m = self._prev_altitude_m + (target_altitude - self._prev_altitude_m) * ramp_frac
        expected = pm.expected_state(rpm, altitude_m, self.config.isa_dev_c, afr, throttle)

        if self.wear_enabled:
            self.wear_elapsed_s += self.dt
        actual = {ch: self._apply_actual(ch, expected[ch]) for ch in self.fluctuation}
        row = {
            "time_s": round(self.time_s, 1),
            "stage": name,
            "rpm": round(rpm, 1),
            "altitude_m": round(altitude_m, 1),
            "ambient_temp_c": expected["ambient_temp_c"],
        }
        for ch in self.fluctuation:
            row[f"expected_{ch}"] = expected[ch]
            row[f"actual_{ch}"] = round(actual[ch], 3)
            row[f"deviation_pct_{ch}"] = round(pm.deviation_pct(actual[ch], expected[ch]), 2)
        row["active_faults"] = list(self.active_faults.keys())
        self.timeseries.append(row)
        self.time_s += self.dt
        self._realtime_stage_elapsed_s += self.dt

        if self._realtime_stage_elapsed_s >= duration_s:
            self.events.append({"time_s": self.time_s, "type": "stage_end", "stage": name})
            self._prev_rpm = target_rpm
            self._prev_altitude_m = target_altitude
            self._realtime_stage_index += 1
            self._realtime_stage_elapsed_s = 0.0
            if self._realtime_stage_index >= len(self.stage_definitions):
                self._realtime_finished = True
                self.events.append({"time_s": self.time_s, "type": "mission_end"})
        return row

    # ------------------------------------------------------------------
    # Core step: produce ONE coherent, fluctuating, fault-affected sample
    # ------------------------------------------------------------------
    def _apply_actual(self, channel: str, expected: float) -> float:
        noise_frac = self.noise[channel].next()
        fault_pct = 0.0
        if channel in self.active_faults:
            fault = self.active_faults[channel]
            fault.step(self.dt)
            fault_pct = fault.current_pct
            if abs(fault.current_pct) < 0.01 and fault.target_pct == 0.0:
                del self.active_faults[channel]

        wear_pct = 0.0
        if self.wear_enabled:
            hours = self.wear_elapsed_s / 3600.0
            direction = -1.0 if channel == "oil_pressure_psi" else 1.0
            wear_pct = direction * self.wear_pct_per_hour * hours

        return expected * (1 + noise_frac) * (1 + fault_pct / 100.0) * (1 + wear_pct / 100.0)

    def _run_stage(self, name, target_rpm, throttle, afr, alt_frac, duration_s):
        target_altitude = stage_altitude_m(alt_frac, self.config.airfield_elevation_m,
                                            self.config.cruise_altitude_m)
        self.events.append({"time_s": self.time_s, "type": "stage_start", "stage": name})

        steps = int(duration_s / self.dt)
        for i in range(steps):
            t_in_stage = i * self.dt
            ramp_frac = min(1.0, t_in_stage / RAMP_TIME_S)
            rpm = self._prev_rpm + (target_rpm - self._prev_rpm) * ramp_frac
            altitude_m = self._prev_altitude_m + (target_altitude - self._prev_altitude_m) * ramp_frac

            expected = pm.expected_state(rpm, altitude_m, self.config.isa_dev_c, afr, throttle)

            if self.wear_enabled:
                self.wear_elapsed_s += self.dt

            actual = {channel: self._apply_actual(channel, expected[channel])
                      for channel in self.fluctuation}

            row = {
                "time_s": round(self.time_s, 1),
                "stage": name,
                "rpm": round(rpm, 1),
                "altitude_m": round(altitude_m, 1),
                "ambient_temp_c": expected["ambient_temp_c"],
            }
            for ch in self.fluctuation:
                row[f"expected_{ch}"] = expected[ch]
                row[f"actual_{ch}"] = round(actual[ch], 3)
                row[f"deviation_pct_{ch}"] = round(pm.deviation_pct(actual[ch], expected[ch]), 2)
            row["active_faults"] = list(self.active_faults.keys())

            self.timeseries.append(row)
            self.time_s += self.dt

        self._prev_rpm = target_rpm
        self._prev_altitude_m = target_altitude
        self.events.append({"time_s": self.time_s, "type": "stage_end", "stage": name})

    def run_full_mission(self):
        for name, rpm, throttle, afr, alt_frac, default_dur in self.stage_definitions:
            duration_s = self.config.duration_for(name, default_dur)
            self._run_stage(name, rpm, throttle, afr, alt_frac, duration_s)

    def run_rapid_throttle_scenario(self, base_rpm=3000, peak_rpm=5800, base_throttle=0.3,
                                     peak_throttle=1.0, hold_low_s=15, transition_s=3, hold_high_s=20,
                                     altitude_m=1000, afr=13.0):
        """Dedicated scenario: fast throttle/RPM step, for transient-response testing."""
        old_ramp = RAMP_TIME_S
        globals()["RAMP_TIME_S"] = transition_s   # sharpen the ramp just for this scenario
        try:
            self._run_stage("RAPID_LOW", base_rpm, base_throttle, afr,
                             (altitude_m - self.config.airfield_elevation_m) /
                             max(1.0, (self.config.cruise_altitude_m - self.config.airfield_elevation_m)),
                             hold_low_s)
            self._run_stage("RAPID_HIGH", peak_rpm, peak_throttle, afr,
                             (altitude_m - self.config.airfield_elevation_m) /
                             max(1.0, (self.config.cruise_altitude_m - self.config.airfield_elevation_m)),
                             hold_high_s)
        finally:
            globals()["RAMP_TIME_S"] = old_ramp

    # ------------------------------------------------------------------
    # Storage -- mission must be saved so replay can READ it, not regenerate it
    # ------------------------------------------------------------------
    def save_mission(self, filepath: str, mission_name: str):
        payload = {
            "mission_name": mission_name,
            "recorded_at_unix": time_module.time(),
            "config": {
                "environment": self.config.environment,
                "environment_label": self.config.label,
                "isa_dev_c": self.config.isa_dev_c,
                "cruise_altitude_m": self.config.cruise_altitude_m,
                "airfield_elevation_m": self.config.airfield_elevation_m,
                "stage_durations_s": self.config.stage_durations_s,
            },
            "duration_s": self.time_s,
            "timeseries": self.timeseries,
            "events": self.events,
        }
        with open(filepath, "w") as f:
            json.dump(payload, f)
        return filepath


if __name__ == "__main__":
    # Demo: full mission on a hot, high-altitude day, with a manual fault
    # injected mid-cruise and endurance wear enabled throughout the loiter.
    config = MissionConfig(
        environment="hot_high_altitude",
        stage_durations_s={
            "GROUND_IDLE": 20, "TAXI": 20, "TAKEOFF": 20, "CLIMB": 60,
            "CRUISE_LOITER": 180, "DESCENT": 40, "LANDING": 20, "SHUTDOWN": 15,
        },
    )
    sim = MissionSimulator(config, dt_s=1.0, seed=42)

    # Run the full mission with endurance wear enabled (3% per hour) and a
    # manual oil‑pressure fault injected midway through the loiter stage.
    # The helper runs the normal stage sequence; we then insert the fault
    # around the middle of the CRUISE_LOITER stage.
    # First, run up to the start of loiter.
    for name, rpm, throttle, afr, alt_frac, _ in config.dataset["stages"][:4]:
        sim._run_stage(name, rpm, throttle, afr, alt_frac, config.duration_for(name, 60))

    # Enable wear for endurance (3% per hour)
    sim.enable_wear(pct_per_hour=3.0)

    # Run first half of loiter, then inject fault, then finish loiter.
    half_loiter = config.duration_for("CRUISE_LOITER", 1800) / 2
    sim._run_stage("CRUISE_LOITER_A", 4200, 0.55, 15.0, 1.0, half_loiter)
    sim.set_fault("oil_pressure_psi", percent=-25.0, ramp_s=10.0)
    sim._run_stage("CRUISE_LOITER_B", 4200, 0.55, 15.0, 1.0, half_loiter)
    sim.clear_fault("oil_pressure_psi", ramp_s=10.0)

    # Finish remaining stages.
    for name, rpm, throttle, afr, alt_frac, _ in config.dataset["stages"][5:]:
        sim._run_stage(name, rpm, throttle, afr, alt_frac, config.duration_for(name, 30))

    path = sim.save_mission("demo_mission.json", "Demo: Hot high-altitude ISR sortie with oil fault")
    print(f"Saved mission to {path}")
    print(f"Total samples: {len(sim.timeseries)}, events: {len(sim.events)}")
    print("\nSample row just before fault:")
    print([r for r in sim.timeseries if r["stage"] == "CRUISE_LOITER_A"][-1])
    print("\nSample row during fault (oil pressure should read well below expected):")
    fault_rows = [r for r in sim.timeseries if r["stage"] == "CRUISE_LOITER_B"]
    print(fault_rows[len(fault_rows) // 2])
    print("\nEvent log:")
    for e in sim.events:
        print(e)
