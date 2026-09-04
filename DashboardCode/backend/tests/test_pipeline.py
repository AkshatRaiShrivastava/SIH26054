from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from can import Message

from backend.can_decoder import CANDecoder, CANMapping
from backend.telemetry_state import TelemetryState
from backend.validator import TelemetryValidator


class TestBackendPipeline(unittest.TestCase):
    def test_decode_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mapping_path = Path(tmp) / "can_mapping.yaml"
            mapping_path.write_text(
                """
signals:
  rpm:
    can_id: 0x100
    unit: rpm
    scale: 1
    min: 0
    max: 7000
  cht:
    can_id: 0x101
    unit: degC
    scale: 0.1
    min: -40
    max: 300
  egt:
    can_id: 0x102
    unit: degC
    scale: 0.1
    min: -40
    max: 1000
  oil_pressure:
    can_id: 0x103
    unit: kPa
    scale: 0.1
    min: 0
    max: 600
  oil_temperature:
    can_id: 0x104
    unit: degC
    scale: 0.1
    min: -40
    max: 200
  fuel_flow:
    can_id: 0x105
    unit: L/h
    scale: 0.01
    min: 0
    max: 100
  vibration:
    can_id: 0x106
    unit: mm/s
    scale: 0.01
    min: 0
    max: 50
  battery_voltage:
    can_id: 0x107
    unit: V
    scale: 0.01
    min: 0
    max: 40
""",
                encoding="utf-8",
            )
            mapping = CANMapping.load(mapping_path)
            decoder = CANDecoder(mapping)
            validator = TelemetryValidator()
            msg = Message(arbitration_id=0x100, data=(3200).to_bytes(2, "big"), is_extended_id=False)
            decoded = decoder.decode(msg)
            self.assertIsNotNone(decoded)
            name, value = decoded
            self.assertEqual(name, "rpm")
            self.assertEqual(value, 3200)
            result = validator.validate(mapping.mappings[0x100], value)
            self.assertTrue(result.valid)

    def test_state_updates_and_health(self) -> None:
        state = TelemetryState(interface="vcan0")
        state.mark_frame(valid=True, known=True)
        snap = state.update({"rpm": 3200, "cht": 158.2, "egt": 710.4, "oil_pressure": 410.2, "oil_temperature": 92.4, "fuel_flow": 18.2, "vibration": 1.21, "battery_voltage": 27.8})
        self.assertEqual(snap.rpm, 3200)
        health = state.health()
        self.assertEqual(health.signals_total, 8)


if __name__ == "__main__":
    unittest.main()
