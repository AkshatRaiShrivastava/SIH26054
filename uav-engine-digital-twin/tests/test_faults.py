from __future__ import annotations

import unittest

from simulator.faults import FaultManager
from simulator.telemetry import EngineTelemetry


class TestFaults(unittest.TestCase):
    def test_injector_degradation_modifiers(self) -> None:
        manager = FaultManager()
        manager.enable("injector_degradation", 0.5)
        mods = manager.get_physics_modifiers()
        self.assertLess(mods["fuel_efficiency"], 1.0)

    def test_lubrication_degradation_modifiers(self) -> None:
        manager = FaultManager()
        manager.enable("lubrication_degradation", 0.7)
        mods = manager.get_physics_modifiers()
        self.assertLess(mods["oil_pressure_base"], 1.0)


if __name__ == "__main__":
    unittest.main()
