from __future__ import annotations

from dataclasses import dataclass


PHASES = {
    0: {"name": "POWER ON", "start": 0, "end": 120},
    1: {"name": "PREFLIGHT CHECK", "start": 120, "end": 300},
    2: {"name": "TAKEOFF", "start": 300, "end": 360},
    3: {"name": "CLIMB", "start": 360, "end": 840},
    4: {"name": "CRUISE / ISR", "start": 840, "end": 3240},
    5: {"name": "DESCEND", "start": 3240, "end": 3540},
    6: {"name": "LAND", "start": 3540, "end": 3600},
}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    onset_s: int = 0
    severity: float = 0.0


SCENARIO_SPECS = {
    "normal": ScenarioSpec("normal", 0, 0.0),
    "injector-degradation": ScenarioSpec("injector-degradation", 1200, 0.5),
    "lubrication-degradation": ScenarioSpec("lubrication-degradation", 900, 0.7),
    "vibration-degradation": ScenarioSpec("vibration-degradation", 1500, 0.6),
    "overheating": ScenarioSpec("overheating", 1000, 0.8),
    "misfire": ScenarioSpec("misfire", 1800, 0.75),
    "electrical-issue": ScenarioSpec("electrical-issue", 1200, 0.55),
    "sensor-drift": ScenarioSpec("sensor-drift", 1100, 0.5),
    "degradation-demo": ScenarioSpec("degradation-demo", 500, 1.0),
}


def phase_for_elapsed(elapsed_s: float) -> int:
    for phase_id, phase in sorted(PHASES.items()):
        if phase["start"] <= elapsed_s < phase["end"]:
            return phase_id
    return 6


def phase_name(phase_id: int) -> str:
    return PHASES.get(phase_id, PHASES[6])["name"]


def elapsed_to_progress(elapsed_s: float) -> float:
    mission_total = 3600.0
    return max(0.0, min(100.0, (elapsed_s / mission_total) * 100.0))
