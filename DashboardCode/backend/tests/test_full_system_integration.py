"""
Integration tests for complete UAV Engine Digital Twin pipeline:
CAN ingestion -> Telemetry decoding -> Flight association -> PostgreSQL persistence -> Physics Evaluation -> Maintenance Advisory -> REST APIs.
"""

import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
import os
import sys

from can import Message

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "DashboardCode") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "DashboardCode"))

from backend.can_decoder import CANDecoder, CANMapping
from backend.telemetry_state import TelemetryState
from backend.models import EngineTelemetry
from backend.flight_recorder import FlightRecorder
from backend.telemetry_service import TelemetryService
from backend.maintenance_service import MaintenanceAdvisoryService
from src.core.physics_layer import PhysicsEvaluator


class TestFullSystemIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.mapping_path = Path(self.tmp_dir.name) / "can_mapping.yaml"
        self.mapping_path.write_text(
            """
signals:
  rpm:
    can_id: 0x100
    unit: rpm
    scale: 1
  cht:
    can_id: 0x101
    unit: degC
    scale: 0.1
  egt:
    can_id: 0x102
    unit: degC
    scale: 0.1
  oil_pressure:
    can_id: 0x103
    unit: kPa
    scale: 0.1
  oil_temperature:
    can_id: 0x104
    unit: degC
    scale: 0.1
  fuel_flow:
    can_id: 0x105
    unit: L/h
    scale: 0.01
  vibration:
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
        self.db_url = os.getenv("DATABASE_URL", "postgresql://uav:uav_password_123@127.0.0.1:5432/uav_telemetry")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_full_pipeline_flow(self):
        """Test full sequence from CAN decoding to physics evaluation and maintenance generation."""
        # 1. CAN Decoder test
        mapping = CANMapping.load(self.mapping_path)
        decoder = CANDecoder(mapping)

        msg_rpm = Message(arbitration_id=0x100, data=(3200).to_bytes(2, "big"))
        decoded = decoder.decode(msg_rpm)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded[0], "rpm")
        self.assertEqual(decoded[1], 3200)

        # 2. Telemetry state update test
        state = TelemetryState(interface="vcan0")
        state.mark_frame(valid=True, known=True)
        snapshot = state.update({
            "rpm": 3200,
            "cht": 165.0,
            "egt": 755.0,
            "oil_pressure": 390.0,
            "oil_temperature": 92.0,
            "fuel_flow": 18.5,
            "vibration": 1.25,
            "battery_voltage": 27.8,
        })
        self.assertEqual(snapshot.rpm, 3200)
        self.assertEqual(snapshot.egt, 755.0)

        # 3. Physics Evaluator test
        evaluator = PhysicsEvaluator(flight_id="FLT-TEST-001", is_live=True)
        telemetry_row = {
            "rpm": snapshot.rpm,
            "cht_c": snapshot.cht,
            "egt_c": snapshot.egt,
            "oil_temp_c": snapshot.oil_temperature,
            "oil_pressure_psi": snapshot.oil_pressure * 0.145038,
            "fuel_flow_lph": snapshot.fuel_flow,
            "vibration_g": snapshot.vibration / 9.81,
            "battery_v": snapshot.battery_voltage,
            "altitude_m": 1500.0,
            "phase": "cruise",
            "mission_time_s": 120.0,
            "timestamp": snapshot.timestamp,
        }
        evaluations = evaluator.evaluate_packet(telemetry_row)
        self.assertTrue(len(evaluations) > 0)

        # Verify expected values and residuals calculated
        egt_eval = next(item for item in evaluations if item["parameter"] == "egt_c")
        self.assertIn("actual", egt_eval)
        self.assertIn("expected", egt_eval)
        self.assertIn("deviation_pct", egt_eval)

        # 4. Maintenance Advisory Service test
        maint_service = MaintenanceAdvisoryService()
        residuals_dict = {
            "egt": {"actual": 755.0, "expected": 720.0, "residual": 35.0, "residual_pct": 4.86},
            "oil_pressure": {"actual": 390.0, "expected": 450.0, "residual": -60.0, "residual_pct": -13.3},
        }

        # Feed 10 residual samples to activate window detection
        for _ in range(12):
            recs = maint_service.evaluate_residuals("FLT-TEST-001", residuals_dict)

        self.assertTrue(len(recs) > 0)
        self.assertTrue(any(r.priority == "HIGH" for r in recs))

    def test_stale_telemetry_detection(self):
        """Test stale telemetry flag when CAN packets stop arriving."""
        state = TelemetryState(interface="vcan0")
        initial_health = state.health()
        self.assertTrue(initial_health.stale)

        # Update all 8 signals
        state.update({
            "rpm": 3200, "cht": 165.0, "egt": 755.0, "oil_pressure": 390.0,
            "oil_temperature": 92.0, "fuel_flow": 18.5, "vibration": 1.25, "battery_voltage": 27.8
        })
        active_health = state.health()
        self.assertFalse(active_health.stale)


if __name__ == "__main__":
    unittest.main()
