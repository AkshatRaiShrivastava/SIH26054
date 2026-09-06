from __future__ import annotations


def deviation_pct(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0
    return ((actual - expected) / expected) * 100.0
