from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from can_interface.can_sender import CANEncoder, CANMapping
from simulator.telemetry import EngineTelemetry


class TestCANMapping(unittest.TestCase):
    def test_yaml_load_and_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mapping_path = Path(tmp) / "can_mapping.yaml"
            mapping_path.write_text(
                """
signals:
  rpm:
    can_id: 0x100
    unit: rpm
    scale: 1
  cht_c:
    can_id: 0x101
    unit: degC
    scale: 0.1
  egt_c:
    can_id: 0x102
    unit: degC
    scale: 0.1
  oil_pressure_kpa:
    can_id: 0x103
    unit: kPa
    scale: 0.1
  oil_temperature_c:
    can_id: 0x104
    unit: degC
    scale: 0.1
  fuel_flow_lph:
    can_id: 0x105
    unit: L/h
    scale: 0.01
  vibration_mms:
    can_id: 0x106
    unit: mm/s
    scale: 0.01
  battery_voltage:
    can_id: 0x107
    unit: V
    scale: 0.01
""",
                encoding="utf-8",
            )
            mapping = CANMapping.load(mapping_path)
            encoder = CANEncoder(mapping)
            telemetry = EngineTelemetry(
                rpm=3150,
                cht_c=158.2,
                egt_c=710.4,
                oil_pressure_kpa=410.2,
                oil_temperature_c=92.4,
                fuel_flow_lph=18.2,
                vibration_mms=1.21,
                battery_voltage=27.8,
            )
            frames = encoder.encode_telemetry(telemetry)
            decoded = encoder.decode_frames(frames)
            self.assertAlmostEqual(decoded["rpm"], 3150)
            self.assertAlmostEqual(decoded["cht_c"], 158.2, places=1)
            self.assertAlmostEqual(decoded["fuel_flow_lph"], 18.2, places=2)


if __name__ == "__main__":
    unittest.main()
