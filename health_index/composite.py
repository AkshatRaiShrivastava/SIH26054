from __future__ import annotations

from physics.config import PHYSICS_CONFIG


def health_index_score(deviation_pcts: list[float], anomaly_score: float) -> float:
    if not deviation_pcts:
        return 100.0
    mean_abs_deviation = sum(abs(v) for v in deviation_pcts) / len(deviation_pcts)
    normalized_anomaly = max(0.0, -anomaly_score)
    penalty = PHYSICS_CONFIG.HEALTH_PENALTY_WEIGHT * mean_abs_deviation + PHYSICS_CONFIG.ANOMALY_WEIGHT * normalized_anomaly
    return max(0.0, PHYSICS_CONFIG.MAX_HEALTH_INDEX - penalty)
