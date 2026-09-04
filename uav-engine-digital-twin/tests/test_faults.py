from __future__ import annotations

import unittest

from simulator.faults import FaultManager
from simulator.telemetry import EngineTelemetry


class TestFaults(unittest.TestCase):
    def test_injector_degradation_changes_telemetry(self) -> None:
        manager = FaultManager()
        manager.enable("injector_degradation", 0.5)
        base = EngineTelemetry(
            rpm=3200,
            cht_c=150,
            egt_c=700,
            oil_pressure_kpa=400,
            oil_temperature_c=90,
            fuel_flow_lph=18,
            vibration_mms=1.0,
            battery_voltage=27.8,
        )
        modified = manager.apply(base, baseline_rpm=3200)
        self.assertGreater(modified.fuel_flow_lph, base.fuel_flow_lph)
        self.assertGreater(modified.egt_c, base.egt_c)
        self.assertGreater(modified.vibration_mms, base.vibration_mms)

    def test_lubrication_problem_reduces_pressure(self) -> None:
        manager = FaultManager()
        manager.enable("lubrication_problem", 0.7)
        base = EngineTelemetry(
            rpm=3200,
            cht_c=150,
            egt_c=700,
            oil_pressure_kpa=400,
            oil_temperature_c=90,
            fuel_flow_lph=18,
            vibration_mms=1.0,
            battery_voltage=27.8,
        )
        modified = manager.apply(base, baseline_rpm=3200)
        self.assertLess(modified.oil_pressure_kpa, base.oil_pressure_kpa)
        self.assertGreater(modified.oil_temperature_c, base.oil_temperature_c)


if __name__ == "__main__":
    unittest.main()
