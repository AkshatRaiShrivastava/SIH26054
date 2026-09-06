"""
Maintenance Advisory Service: Generates engineering advisories based on physics residuals and state dynamics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


@dataclass
class MaintenanceRecommendation:
    component: str
    priority: str  # "HIGH", "MEDIUM", "LOW", "ADVISORY"
    reason: str
    evidence: str
    recommendation: str
    status: str = "OPEN"
    due_hours: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MaintenanceAdvisoryService:
    """
    Backend service analyzing physics residuals, health trends, and engine operational telemetry.
    Produces engineering advisories without declaring false component failures on single readings.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Residual window history per signal for persistence tracking
        self._residual_history: Dict[str, List[float]] = {
            "egt": [],
            "cht": [],
            "oil_pressure": [],
            "oil_temperature": [],
            "fuel_flow": [],
            "vibration": [],
        }
        self._history_limit = 30  # ~3 seconds at 10Hz

    def evaluate_residuals(
        self,
        flight_id: str,
        residuals: Dict[str, Dict[str, float]],
        health_score: float = 100.0,
        anomaly_score: float = 0.0,
    ) -> List[MaintenanceRecommendation]:
        """
        Evaluates current physics residuals and produces structured advisories.

        residuals schema expected:
        {
          "egt": {"actual": 755.0, "expected": 720.0, "residual": 35.0, "residual_pct": 4.86},
          "oil_pressure": {"actual": 390.0, "expected": 410.0, "residual": -20.0, "residual_pct": -4.88},
          ...
        }
        """
        with self._lock:
            recommendations: List[MaintenanceRecommendation] = []

            # Track window history
            for sig, data in residuals.items():
                if sig in self._residual_history:
                    res_val = data.get("residual_pct", 0.0)
                    self._residual_history[sig].append(res_val)
                    if len(self._residual_history[sig]) > self._history_limit:
                        self._residual_history[sig].pop(0)

            # 1. Lubrication system analysis
            oil_p_history = self._residual_history.get("oil_pressure", [])
            if len(oil_p_history) >= 10:
                avg_oil_p_res = sum(oil_p_history[-10:]) / 10.0
                if avg_oil_p_res < -8.0:
                    recommendations.append(
                        MaintenanceRecommendation(
                            component="Lubrication System",
                            priority="HIGH",
                            reason="Persistent oil-pressure deviation below expected model baseline.",
                            evidence=f"Oil pressure average residual is {avg_oil_p_res:.1f}% below model expectation over last sample window.",
                            recommendation="Inspect lubrication pump, relief valve, and oil filter condition.",
                            due_hours=10.0,
                        )
                    )

            # 2. Fuel Injector & Combustion analysis
            egt_history = self._residual_history.get("egt", [])
            ff_history = self._residual_history.get("fuel_flow", [])
            if len(egt_history) >= 10:
                avg_egt_res = sum(egt_history[-10:]) / 10.0
                avg_ff_res = (sum(ff_history[-10:]) / 10.0) if ff_history else 0.0

                if avg_egt_res > 5.0 and avg_ff_res > 3.0:
                    recommendations.append(
                        MaintenanceRecommendation(
                            component="Injector / Combustion Chamber",
                            priority="MEDIUM",
                            reason="Fuel flow and EGT residuals concurrently elevated over time.",
                            evidence=f"EGT residual at +{avg_egt_res:.1f}% with Fuel Flow residual at +{avg_ff_res:.1f}%.",
                            recommendation="Inspect fuel injector spray patterns and combustion chamber condition.",
                            due_hours=25.0,
                        )
                    )

            # 3. Cooling system analysis
            cht_history = self._residual_history.get("cht", [])
            oil_t_history = self._residual_history.get("oil_temperature", [])
            if len(cht_history) >= 10:
                avg_cht_res = sum(cht_history[-10:]) / 10.0
                avg_oil_t_res = (sum(oil_t_history[-10:]) / 10.0) if oil_t_history else 0.0

                if avg_cht_res > 7.0 or avg_oil_t_res > 7.0:
                    recommendations.append(
                        MaintenanceRecommendation(
                            component="Cooling System",
                            priority="MEDIUM",
                            reason="Engine thermal state residual exceeds nominal envelope.",
                            evidence=f"CHT residual: +{avg_cht_res:.1f}%, Oil Temp residual: +{avg_oil_t_res:.1f}%.",
                            recommendation="Inspect cooling ducting, airflow baffles, and radiator heat exchangers.",
                            due_hours=20.0,
                        )
                    )

            # 4. Mechanical & Vibration system analysis
            vib_history = self._residual_history.get("vibration", [])
            if len(vib_history) >= 10:
                avg_vib_res = sum(vib_history[-10:]) / 10.0
                if avg_vib_res > 15.0:
                    recommendations.append(
                        MaintenanceRecommendation(
                            component="Mechanical / Vibration System",
                            priority="HIGH",
                            reason="Elevated vibration signature detected.",
                            evidence=f"Vibration residual average is +{avg_vib_res:.1f}% above expected baseline.",
                            recommendation="Perform mechanical vibration spectrum check, inspect engine mounts and propeller balancing.",
                            due_hours=5.0,
                        )
                    )

            # 5. Routine maintenance advisory if no high severity detected
            if not recommendations:
                recommendations.append(
                    MaintenanceRecommendation(
                        component="General Engine Assembly",
                        priority="LOW",
                        reason="All monitored physics residuals remain within baseline engineering tolerances.",
                        evidence=f"Engine health score: {health_score:.1f}%, Anomaly score: {anomaly_score:.1f}%.",
                        recommendation="Continue standard pre-flight inspection procedures.",
                        due_hours=50.0,
                    )
                )

            return recommendations
