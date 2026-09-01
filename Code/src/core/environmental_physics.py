"""
STEP 4: Environmental corrections for physics_layer.py

This module extends the physics layer with:
- Density altitude correction
- Icing risk classification
- Fault attribution override (e.g., "probable induction icing")
- Dust/filter-loading drift
- Corrosion index tracking
"""

import json
import sys
import os
from typing import Dict, Tuple

# Add project root to path if needed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    # Try relative imports first (when run as module)
    from ..utils import config
    from ..utils.utils import (
        compute_density_altitude,
        classify_icing_risk,
        apply_filter_degradation,
    )
except (ImportError, ValueError):
    # Fall back to absolute imports
    from src.utils import config
    from src.utils.utils import (
        compute_density_altitude,
        classify_icing_risk,
        apply_filter_degradation,
    )


class EnvironmentalPhysics:
    """Applies environmental corrections to physics evaluations."""

    def __init__(self):
        """Initialize environmental physics module."""
        self.airframe_corrosion = {}  # {airframe_id: corrosion_index}

    def compute_density_altitude_correction(
        self, altitude_m: float, ambient_temp_c: float, pressure_altitude_m: float
    ) -> Tuple[float, float]:
        """
        Compute density altitude and apply power-loss correction.

        Args:
            altitude_m: geometric altitude (m)
            ambient_temp_c: outside air temperature (°C)
            pressure_altitude_m: pressure altitude (m)

        Returns:
            (density_altitude_m, power_loss_factor)
        """
        da = compute_density_altitude(altitude_m, ambient_temp_c, pressure_altitude_m)

        # Power loss correction
        # Only apply to naturally-aspirated engines; turbocharged (914) compensates
        power_loss_factor = 1.0
        if not config.ENGINE_CONFIG.get("type") == "turbocharged":
            # 3 hp per 1000 ft for O-320 and similar
            power_loss_hp_per_1000ft = config.POWER_LOSS_CORRECTION.get(
                "naturally_aspirated", 0
            )
            da_ft = da * 3.28084  # meters to feet
            power_loss_hp = (da_ft / 1000.0) * power_loss_hp_per_1000ft
            nominal_hp = config.ENGINE_CONFIG.get("nominal_power_hp", 115)
            power_loss_factor = 1.0 - (power_loss_hp / nominal_hp)

        return da, max(0.1, power_loss_factor)  # floor at 10%

    def classify_icing_risk(
        self, ambient_temp_c: float, humidity_pct: float
    ) -> str:
        """
        Classify icing risk from temperature and humidity.

        Args:
            ambient_temp_c: outside air temperature (°C)
            humidity_pct: relative humidity (%)

        Returns:
            "HIGH", "MODERATE", or "LOW"
        """
        return classify_icing_risk(
            ambient_temp_c,
            humidity_pct,
            high_threshold_temp_min=config.ICING_RISK["high"]["temp_min_c"],
            high_threshold_temp_max=config.ICING_RISK["high"]["temp_max_c"],
            high_threshold_humidity=config.ICING_RISK["high"]["humidity_min_pct"],
            moderate_threshold_humidity=config.ICING_RISK["moderate"]["humidity_min_pct"],
        )

    def attribute_fault_with_icing_override(
        self,
        fault_parameter: str,
        fault_status: str,
        icing_risk: str,
        fuel_flow_deviation: float,
        rpm: float,
        egt_deviation: float,
    ) -> str:
        """
        Apply icing-aware fault attribution override.

        Example: if fuel flow is low + icing risk is HIGH + EGT is drifting
        consistently, classify as "probable induction icing" instead of
        "injector abnormality".

        Args:
            fault_parameter: which parameter triggered the fault diagnosis
            fault_status: "caution" or "critical"
            icing_risk: "HIGH", "MODERATE", or "LOW"
            fuel_flow_deviation: fuel flow deviation %
            rpm: current RPM
            egt_deviation: EGT deviation %

        Returns:
            fault category label (or None if not a diagnosed fault)
        """
        if fault_parameter == "fuel_flow_lph" and fault_status in ["caution", "critical"]:
            # Low fuel flow + high icing = probable icing
            if icing_risk == "HIGH" and fuel_flow_deviation < -5 and 4000 < rpm < 5000:
                return "probable_induction_icing"
            # Low fuel flow + normal conditions = injector/supply issue
            if fuel_flow_deviation < -10:
                return "fuel_system_degradation"

        if fault_parameter == "egt_c":
            if fault_status == "critical" and egt_deviation > 20:
                return "combustion_anomaly"

        if fault_parameter == "oil_pressure_psi":
            if fault_status in ["caution", "critical"]:
                return "lubrication_system_failure"

        if fault_parameter == "vibration_g":
            if fault_status == "critical":
                return "mechanical_stress"

        return None

    def apply_filter_degradation_correction(
        self,
        expected_fuel_flow: float,
        hours_since_service: float,
        climate_zone: str,
    ) -> float:
        """
        Adjust expected fuel flow for filter clogging over time.

        Args:
            expected_fuel_flow: nominal expected fuel flow (L/h)
            hours_since_service: flight hours since last filter service
            climate_zone: climate zone (affects dust accumulation rate)

        Returns:
            adjusted expected fuel flow (L/h)
        """
        return apply_filter_degradation(
            expected_fuel_flow,
            hours_since_service,
            climate_zone,
            dust_factor=config.DUST_FILTER_PARAMS["k_dust"],
            fuel_flow_sensitivity=config.DUST_FILTER_PARAMS["fuel_flow_sensitivity"],
        )

    def update_corrosion_index(
        self, airframe_id: str, maritime_hours_cumulative: float
    ) -> float:
        """
        Update and return corrosion index for a given airframe.

        Corrosion is persistent across flights, tracked per airframe.

        Args:
            airframe_id: persistent airframe identifier
            maritime_hours_cumulative: total maritime hours for this airframe

        Returns:
            current corrosion index (0-100+, advisory at ~50)
        """
        corrosion_rate = config.CORROSION_PARAMS["rate_per_hour"]
        corrosion_index = maritime_hours_cumulative * corrosion_rate

        self.airframe_corrosion[airframe_id] = corrosion_index
        return corrosion_index

    def get_corrosion_advisory(self, corrosion_index: float) -> str:
        """
        Generate maintenance advisory based on corrosion index.

        Args:
            corrosion_index: current corrosion index

        Returns:
            advisory level ("NORMAL", "MONITOR", "MAINTENANCE_RECOMMENDED")
        """
        threshold = config.CORROSION_PARAMS["maintenance_threshold"]

        if corrosion_index < threshold * 0.5:
            return "NORMAL"
        elif corrosion_index < threshold:
            return "MONITOR"
        else:
            return "MAINTENANCE_RECOMMENDED"


if __name__ == "__main__":
    env_phys = EnvironmentalPhysics()

    # Test density altitude
    da, pwr = env_phys.compute_density_altitude_correction(3000, 5, 2900)
    print(f"Density altitude test: DA={da:.0f}m, Power factor={pwr:.2f}")

    # Test icing risk
    risk = env_phys.classify_icing_risk(5, 60)
    print(f"Icing risk test: {risk} (should be HIGH)")

    # Test corrosion
    corr = env_phys.update_corrosion_index("AIRFRAME-001", 100)
    advisory = env_phys.get_corrosion_advisory(corr)
    print(f"Corrosion test: index={corr:.1f}, advisory={advisory}")
