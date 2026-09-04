from __future__ import annotations

import unittest

from simulator.engine_model import EngineModel
from simulator.telemetry import EngineInputs


class TestEngineModel(unittest.TestCase):
    def test_throttle_increases_rpm(self) -> None:
        model = EngineModel()
        low = model.step(EngineInputs(throttle=0.2, engine_load=0.3), dt=0.1)
        high = model.step(EngineInputs(throttle=0.9, engine_load=0.3), dt=0.1)
        self.assertGreater(high.rpm, low.rpm)

    def test_altitude_reduces_performance(self) -> None:
        sea_model = EngineModel()
        high_model = EngineModel()
        sea_level = sea_model.step(EngineInputs(throttle=0.7, altitude_m=0.0, engine_load=0.5), dt=0.1)
        high_alt = high_model.step(EngineInputs(throttle=0.7, altitude_m=4000.0, engine_load=0.5), dt=0.1)
        self.assertLess(high_alt.rpm, sea_level.rpm)


if __name__ == "__main__":
    unittest.main()
