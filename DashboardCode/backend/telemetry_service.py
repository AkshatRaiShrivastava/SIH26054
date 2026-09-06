"""
Telemetry Service: Real-time pipeline from SocketCAN to PostgreSQL.

Data Flow:
SocketCAN (vcan0) -> CAN Decoder -> Telemetry State -> Physics Layer -> PostgreSQL
"""

from __future__ import annotations

import threading
import can
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from .can_decoder import CANMapping, CANDecoder
from .telemetry_state import TelemetryState
from .flight_recorder import FlightRecorder
from src.core.physics_layer import PhysicsEvaluator
from src.core.environmental_physics import EnvironmentalPhysics
from .maintenance_service import MaintenanceAdvisoryService


class TelemetryService:
    """
    Backend service that consumes telemetry from SocketCAN,
    evaluates it through the physics layer, and persists it to PostgreSQL.
    """
    def __init__(
        self,
        interface: str,
        mapping_path: Path,
        recorder: FlightRecorder
    ) -> None:
        self.interface = interface
        self.recorder = recorder

        # Initialize Decoder
        self.mapping = CANMapping.load(mapping_path)
        self.decoder = CANDecoder(self.mapping)

        # State Management
        self.state = TelemetryState(interface=interface)
        self.env_physics = EnvironmentalPhysics()

        # Evaluation & Maintenance
        self.evaluator = PhysicsEvaluator(flight_id=recorder.flight_id or "FLT-LIVE", is_live=True)
        self.maintenance_service = MaintenanceAdvisoryService()

        # Latest live evaluation state
        self.latest_physics_results: Dict[str, Dict[str, Any]] = {}
        self.latest_maintenance_records: list = []

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the CAN listener thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"Telemetry Service started. Listening on CAN interface {self.interface}...")

    def stop(self) -> None:
        """Stop the CAN listener."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        """CAN listener loop."""
        try:
            # Initialize CAN bus using socketcan interface
            bus = can.interface.Bus(channel=self.interface, interface='socketcan', socket_can_timeout=1.0)
        except Exception as e:
            print(f"Failed to connect to CAN interface {self.interface}: {e}")
            return

        while not self._stop_event.is_set():
            try:
                message = bus.recv(timeout=1.0)
                if message is None:
                    continue

                # 1. Decode the frame
                decoded = self.decoder.decode(message)
                if decoded is None:
                    self.state.mark_frame(known=False)
                    continue

                signal_name, value = decoded

                # Normalize signal names to match TelemetryState (e.g., cht_c -> cht)
                # Mapping: { 'cht_c': 'cht', 'egt_c': 'egt', ... }
                norm_name = signal_name.replace("_c", "").replace("_kpa", "").replace("_mms", "").replace("_lph", "").replace("_voltage", "")
                # Special cases
                if norm_name == "oil_pressure": pass
                elif norm_name == "oil_temperature": pass
                elif norm_name == "battery": norm_name = "battery_voltage"

                # Update state
                # We check if the signal is one of the tracked signals
                from .telemetry_state import SIGNAL_NAMES
                if norm_name not in SIGNAL_NAMES:
                    self.state.mark_frame(known=False)
                    continue

                self.state.mark_frame(valid=True, known=True)

                # Update the internal values
                telemetry_update = {norm_name: value}
                snapshot = self.state.update(telemetry_update)

                # 2. Record to DB and Evaluate Physics
                # We record a snapshot when all signals have arrived
                if self.recorder.record_signal(signal_name, snapshot):
                    # A full snapshot was just recorded; evaluate it
                    self._evaluate_and_persist(snapshot)

            except Exception as e:
                print(f"Error processing CAN frame: {e}")

        bus.shutdown()

    def _evaluate_and_persist(self, snapshot) -> None:
        """
        Converts EngineTelemetry to format expected by PhysicsEvaluator,
        runs evaluation, persists physics results & maintenance advisories to DB.
        """
        # Map numeric stage ID back to name
        stage_map = {
            0: "OFF", 1: "PRE_FLIGHT", 2: "ENGINE_START", 3: "WARMUP",
            4: "TAXI", 5: "TAKEOFF", 6: "INITIAL_CLIMB", 7: "CLIMB",
            8: "CRUISE_CLIMB", 9: "CRUISE", 10: "HIGH_ALTITUDE_CRUISE",
            11: "LOITER", 12: "DESCENT", 13: "APPROACH", 14: "LANDING",
            15: "COOLDOWN", 16: "SHUTDOWN", 17: "POST_FLIGHT", 18: "MISSION_COMPLETE",
            99: "THROTTLE_TRANSITION"
        }
        current_phase = stage_map.get(int(snapshot.mission_stage), "UNKNOWN")

        telemetry_row = {
            "rpm": snapshot.rpm,
            "cht_c": snapshot.cht,
            "egt_c": snapshot.egt,
            "oil_temp_c": snapshot.oil_temperature,
            "oil_pressure_psi": snapshot.oil_pressure * 0.145038,  # kPa to psi
            "fuel_flow_lph": snapshot.fuel_flow,
            "vibration_g": snapshot.vibration / 9.81,  # mms to g (approx)
            "battery_v": snapshot.battery_voltage,
            "altitude_m": snapshot.altitude,
            "throttle": snapshot.throttle,
            "engine_load": snapshot.load,
            "phase": current_phase,
            "mission_time_s": time.monotonic() - (self.recorder._started_monotonic or time.monotonic()),
            "timestamp": snapshot.timestamp,
        }

        # Update evaluator flight_id if active
        if self.recorder.flight_id:
            self.evaluator.flight_id = self.recorder.flight_id

        # 1. Run physics evaluator
        evaluations = self.evaluator.evaluate_packet(telemetry_row)

        eval_dict = {}
        residuals_dict = {}
        for ev in evaluations:
            param = ev["parameter"]
            actual = ev["actual"]
            expected = ev["expected"]
            residual = actual - expected
            res_pct = ev["deviation_pct"]
            status = ev["status"]

            eval_dict[param] = {
                "actual": actual,
                "expected": expected,
                "residual": residual,
                "residual_pct": res_pct,
                "status": status,
            }
            residuals_dict[param] = {
                "actual": actual,
                "expected": expected,
                "residual": residual,
                "residual_pct": res_pct,
            }

            # Persist physics result if active flight
            if self.recorder.flight_id:
                self.recorder.record_physics_result(
                    flight_id=self.recorder.flight_id,
                    timestamp=snapshot.timestamp,
                    signal_name=param,
                    actual=actual,
                    expected=expected,
                    residual=residual,
                    residual_pct=res_pct,
                    status=status,
                    mission_time_s=telemetry_row["mission_time_s"],
                )

        self.latest_physics_results = eval_dict

        # 2. Run maintenance advisory evaluation
        active_flight = self.recorder.flight_id or "FLT-LIVE"
        maint_recs = self.maintenance_service.evaluate_residuals(
            flight_id=active_flight,
            residuals=residuals_dict,
        )
        self.latest_maintenance_records = maint_recs

        if self.recorder.flight_id:
            for rec in maint_recs:
                if rec.priority in ["HIGH", "MEDIUM"]:
                    self.recorder.record_maintenance_recommendation(
                        flight_id=self.recorder.flight_id,
                        component=rec.component,
                        recommendation=rec.recommendation,
                        priority=rec.priority,
                        reason=rec.reason,
                        evidence=rec.evidence,
                        due_hours=rec.due_hours,
                    )
