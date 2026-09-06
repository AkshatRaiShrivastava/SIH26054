from __future__ import annotations

from simulator.mission_profile import PHASES, phase_for_elapsed


def advance_phase(elapsed_s: float, current_phase: int):
    target = phase_for_elapsed(elapsed_s)
    return target if target != current_phase else current_phase
