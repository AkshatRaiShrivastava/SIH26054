"""
physics_layer.py — STEP 2: Engine-only physics evaluation with debounced status.

Evaluates actual vs. expected engine parameters and produces debounced health status.
Addresses the consistency/flicker requirement via rolling-window debouncing.

Usage:
    # Live mode (concurrent with generate_telemetry.py)
    python -m src.core.physics_layer --flight-id FL-2026-08-30-001 --live

    # Replay mode (evaluate an already-complete flight)
    python -m src.core.physics_layer --flight-id FL-2026-08-30-001 --replay
"""

import argparse
import json
import sqlite3
import sys
import os
import time
from datetime import datetime
from collections import defaultdict

# Add project root to path if running directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    # Try relative imports first (when run as module)
    from ..utils import config
    from ..database.database import get_connection, close_connection
    from .environmental_physics import EnvironmentalPhysics
except (ImportError, ValueError):
    # Fall back to absolute imports (when run directly)
    from src.utils import config
    from src.database.database import get_connection, close_connection
    from src.core.environmental_physics import EnvironmentalPhysics


class PhysicsEvaluator:
    """Evaluates telemetry against physics models and produces debounced health status."""

    def __init__(self, flight_id: str, is_live: bool = False):
        """
        Initialize evaluator.

        Args:
            flight_id: flight to evaluate
            is_live: True for live mode (polling), False for replay mode
        """
        self.flight_id = flight_id
        self.is_live = is_live

        # Environmental physics corrections
        self.env_physics = EnvironmentalPhysics()

        # Debounce tracking per parameter
        self.status_history = defaultdict(lambda: [])  # {param: [status, status, ...]}

        # Last processed mission_time_s (for live mode)
        self.last_processed_time_s = -1.0

        print(
            f"Evaluator initialized: {flight_id} ({['replay', 'live'][is_live]} mode)"
        )

    def compute_expected_values(self, telemetry_row: dict) -> dict:
        """
        Compute expected values for engine parameters based on phase and conditions.
        (Engine-only for Step 2; environmental corrections added in Step 4)

        Args:
            telemetry_row: dict with telemetry fields from database

        Returns:
            dict of {parameter: expected_value}
        """
        expected = {}
        rpm = telemetry_row["rpm"]
        altitude_m = telemetry_row["altitude_m"]
        phase = telemetry_row["phase"]

        # Baseline expected values (from config, adjusted by phase and RPM)
        rpm_factor = rpm / config.EXPECTED_VALUES_NOMINAL["rpm"]

        for param, nominal_value in config.EXPECTED_VALUES_NOMINAL.items():
            if param == "rpm":
                expected[param] = rpm
            elif param in ["cht_c", "egt_c", "oil_temp_c"]:
                # Temperatures increase slightly with higher RPM and altitude
                expected[param] = nominal_value * (0.95 + 0.05 * rpm_factor)
            elif param == "oil_pressure_psi":
                # Pressure is RPM-dependent
                expected[param] = nominal_value * (0.5 + 0.5 * rpm_factor)
            elif param == "fuel_flow_lph":
                # Fuel flow scales with RPM
                expected[param] = nominal_value * rpm_factor
            elif param == "vibration_g":
                # Vibration generally increases with RPM
                expected[param] = nominal_value * (0.3 + 0.7 * rpm_factor)
            elif param == "battery_v":
                # Stable around nominal
                expected[param] = nominal_value
            elif param == "afr":
                # Air/fuel ratio, relatively stable
                expected[param] = nominal_value
            else:
                expected[param] = nominal_value

        return expected

    def compute_deviation(self, actual: float, expected: float) -> float:
        """
        Compute deviation as a percentage.

        Args:
            actual: actual value from telemetry
            expected: computed expected value

        Returns:
            deviation as % (positive = higher than expected)
        """
        if expected == 0:
            return 0.0
        return 100 * (actual - expected) / expected

    def raw_status_from_deviation(self, parameter: str, deviation_pct: float) -> str:
        """
        Classify single-packet status (before debouncing).

        Args:
            parameter: parameter name
            deviation_pct: computed deviation %

        Returns:
            "normal" | "caution" | "critical"
        """
        # For pressure/flow: negative deviation is bad
        # For temp/vibration: positive deviation is bad
        is_negative_bad = parameter in ["oil_pressure_psi", "fuel_flow_lph", "battery_v"]

        if is_negative_bad:
            deviation_abs = -deviation_pct
        else:
            deviation_abs = deviation_pct

        if deviation_abs < config.DEBOUNCE_CONFIG["status_thresholds"]["normal_to_caution"]:
            return "normal"
        elif (
            deviation_abs
            < config.DEBOUNCE_CONFIG["status_thresholds"]["caution_to_critical"]
        ):
            return "caution"
        else:
            return "critical"

    def debounce_status(
        self, parameter: str, raw_status: str
    ) -> str:
        """
        Apply debouncing to prevent flicker.
        A status change only takes effect once N consecutive packets agree.

        Args:
            parameter: parameter name
            raw_status: single-packet status ("normal"|"caution"|"critical")

        Returns:
            debounced status (same as raw_status if enough consensus, else prior status)
        """
        window_size = config.DEBOUNCE_CONFIG["window_packets"]
        threshold = config.DEBOUNCE_CONFIG["threshold_packets"]

        # Add new status to history
        history = [raw_status] + self.status_history[parameter]
        history = history[:window_size]
        self.status_history[parameter] = history

        # Count agreement on new status
        count_agree = sum(1 for s in history if s == raw_status)

        if count_agree >= threshold:
            # New status has consensus
            debounced = raw_status
        else:
            # Insufficient consensus; use previous debounced status
            debounced = history[1] if len(history) > 1 else raw_status

        return debounced

    def evaluate_packet(self, telemetry_row: dict) -> dict:
        """
        Evaluate a single telemetry packet.

        Args:
            telemetry_row: dict from telemetry table

        Returns:
            dict with all evaluation fields (ready to insert into evaluations table)
        """
        # Compute expected values
        expected_vals = self.compute_expected_values(telemetry_row)

        # Evaluate each parameter
        evaluations = []
        for param, expected_val in expected_vals.items():
            actual_val = telemetry_row.get(param, 0)
            deviation = self.compute_deviation(actual_val, expected_val)
            raw_status = self.raw_status_from_deviation(param, deviation)
            debounced = self.debounce_status(param, raw_status)

            evaluation = {
                "flight_id": self.flight_id,
                "mission_time_s": telemetry_row["mission_time_s"],
                "timestamp": telemetry_row["timestamp"],
                "parameter": param,
                "actual": actual_val,
                "expected": expected_val,
                "deviation_pct": deviation,
                "raw_status": raw_status,
                "status": debounced,
            }
            evaluations.append(evaluation)

        return evaluations

    def compute_subsystem_health(
        self, parameter_statuses: dict
    ) -> dict:
        """
        Compute health score for each subsystem based on parameter statuses.

        Args:
            parameter_statuses: {param: status} from a single evaluation

        Returns:
            {subsystem_name: health_score (0-100)}
        """
        subsystem_health = {}

        for subsystem, params in config.SUBSYSTEM_PARAMETERS.items():
            # Collect statuses for this subsystem's parameters
            subsys_statuses = [
                parameter_statuses.get(p, "normal") for p in params
            ]

            # Score: normal=100, caution=60, critical=0
            status_scores = {
                "normal": 100,
                "caution": 60,
                "critical": 0,
            }

            scores = [status_scores.get(s, 100) for s in subsys_statuses]
            health = sum(scores) / len(scores) if scores else 100

            subsystem_health[subsystem] = round(health, 1)

        return subsystem_health

    def compute_overall_status(self, subsystem_health: dict) -> str:
        """
        Compute overall status from subsystem health scores.

        Args:
            subsystem_health: {subsystem: score (0-100)}

        Returns:
            "normal" | "caution" | "critical"
        """
        # Weighted average
        total_score = 0
        total_weight = 0

        for subsystem, score in subsystem_health.items():
            weight = config.SUBSYSTEM_WEIGHTS.get(subsystem, 0.25)
            total_score += score * weight
            total_weight += weight

        overall_score = (
            total_score / total_weight if total_weight > 0 else 100
        )

        if overall_score >= 90:
            return "normal"
        elif overall_score >= 50:
            return "caution"
        else:
            return "critical"

    def process_flight(self, db_path: str = "digital_twin.db"):
        """
        Process a flight: read telemetry, evaluate, write results.

        Args:
            db_path: path to SQLite database
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            if self.is_live:
                self._process_live(cursor, conn)
            else:
                self._process_replay(cursor, conn)
        finally:
            close_connection(conn)

    def _process_replay(self, cursor, conn):
        """Process a complete flight's history in one pass."""
        print("Processing complete flight...")

        # Fetch flight info and all telemetry
        cursor.execute(
            "SELECT * FROM flights WHERE flight_id = ?", (self.flight_id,)
        )
        flight_row = cursor.fetchone()
        if not flight_row:
            print(f"Flight {self.flight_id} not found")
            return

        flight_col_names = [desc[0] for desc in cursor.description]
        flight_info = dict(zip(flight_col_names, flight_row))

        # Fetch telemetry
        cursor.execute(
            "SELECT * FROM telemetry WHERE flight_id = ? ORDER BY mission_time_s ASC",
            (self.flight_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            print(f"No telemetry found for flight {self.flight_id}")
            return

        # Get column names
        col_names = [desc[0] for desc in cursor.description]

        packet_count = 0
        for row in rows:
            # Convert row tuple to dict
            telemetry_row = dict(zip(col_names, row))

            # Evaluate packet
            evaluations = self.evaluate_packet(telemetry_row)

            # Write evaluations
            for eval_data in evaluations:
                cursor.execute(
                    """
                    INSERT INTO evaluations (
                        flight_id, mission_time_s, timestamp, parameter,
                        actual, expected, deviation_pct, raw_status, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        eval_data["flight_id"],
                        eval_data["mission_time_s"],
                        eval_data["timestamp"],
                        eval_data["parameter"],
                        eval_data["actual"],
                        eval_data["expected"],
                        eval_data["deviation_pct"],
                        eval_data["raw_status"],
                        eval_data["status"],
                    ),
                )

            # Compute icing risk
            ambient_temp = telemetry_row.get("ambient_temp_c", 15)
            humidity = telemetry_row.get("humidity_pct", 50)
            icing_advisory = self.env_physics.classify_icing_risk(ambient_temp, humidity)

            # Compute corrosion index (environmental advisory layer)
            maritime_hours = telemetry_row.get("maritime_hours_cumulative", 0)
            airframe_id = flight_info.get("airframe_id", config.DEFAULT_AIRFRAME_ID)
            corrosion_index = self.env_physics.update_corrosion_index(
                airframe_id, maritime_hours
            )
            corrosion_advisory = self.env_physics.get_corrosion_advisory(corrosion_index)

            # Attribute fault if one was injected
            fault_parameter = flight_info.get("fault_injected")
            fault_category = None
            if fault_parameter:
                # Find this parameter's status and deviations
                param_eval = next(
                    (e for e in evaluations if e["parameter"] == fault_parameter), None
                )
                if param_eval:
                    fault_category = self.env_physics.attribute_fault_with_icing_override(
                        fault_parameter=fault_parameter,
                        fault_status=param_eval["status"],
                        icing_risk=icing_advisory,
                        fuel_flow_deviation=next(
                            (e["deviation_pct"] for e in evaluations if e["parameter"] == "fuel_flow_lph"),
                            0,
                        ),
                        rpm=telemetry_row.get("rpm", 2000),
                        egt_deviation=next(
                            (e["deviation_pct"] for e in evaluations if e["parameter"] == "egt_c"), 0
                        ),
                    )

            # Compute flight condition
            parameter_statuses = {e["parameter"]: e["status"] for e in evaluations}
            subsys_health = self.compute_subsystem_health(parameter_statuses)
            overall_status = self.compute_overall_status(subsys_health)

            cursor.execute(
                """
                INSERT INTO flight_condition (
                    flight_id, mission_time_s, timestamp,
                    subsystem_health_json, overall_status, icing_advisory, fault_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.flight_id,
                    telemetry_row["mission_time_s"],
                    telemetry_row["timestamp"],
                    json.dumps(subsys_health),
                    overall_status,
                    icing_advisory,
                    fault_category,
                ),
            )

            packet_count += 1
            if packet_count % 20 == 0:
                print(
                    f"  [{packet_count}] Mission time: {telemetry_row['mission_time_s']/60:.1f} min, "
                    f"Overall: {overall_status}, Health: {subsys_health}, "
                    f"Icing: {icing_advisory}"
                )

        conn.commit()
        print(f"Replay complete: {packet_count} packets evaluated")

    def _process_live(self, cursor, conn):
        """Process a live flight by polling for new telemetry."""
        print("Entering live polling mode (Ctrl+C to stop)...")
        print("Waiting for telemetry packets...")

        # Fetch flight info once
        cursor.execute(
            "SELECT * FROM flights WHERE flight_id = ?", (self.flight_id,)
        )
        flight_row = cursor.fetchone()
        if not flight_row:
            print(f"Flight {self.flight_id} not found")
            return

        flight_col_names = [desc[0] for desc in cursor.description]
        flight_info = dict(zip(flight_col_names, flight_row))

        try:
            while True:
                # Query for new telemetry since last processed time
                cursor.execute(
                    """
                    SELECT * FROM telemetry
                    WHERE flight_id = ? AND mission_time_s > ?
                    ORDER BY mission_time_s ASC
                """,
                    (self.flight_id, self.last_processed_time_s),
                )
                rows = cursor.fetchall()

                if not rows:
                    # Check if flight is complete
                    cursor.execute(
                        "SELECT status FROM flights WHERE flight_id = ?",
                        (self.flight_id,),
                    )
                    result = cursor.fetchone()
                    if result and result[0] == "complete":
                        print("Flight marked complete, exiting live mode")
                        break
                    # No new data yet, sleep and retry
                    time.sleep(1)
                    continue

                # Get column names
                col_names = [desc[0] for desc in cursor.description]

                for row in rows:
                    # Convert to dict
                    telemetry_row = dict(zip(col_names, row))

                    # Evaluate
                    evaluations = self.evaluate_packet(telemetry_row)

                    # Write evaluations
                    for eval_data in evaluations:
                        cursor.execute(
                            """
                            INSERT INTO evaluations (
                                flight_id, mission_time_s, timestamp, parameter,
                                actual, expected, deviation_pct, raw_status, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                eval_data["flight_id"],
                                eval_data["mission_time_s"],
                                eval_data["timestamp"],
                                eval_data["parameter"],
                                eval_data["actual"],
                                eval_data["expected"],
                                eval_data["deviation_pct"],
                                eval_data["raw_status"],
                                eval_data["status"],
                            ),
                        )

                    # Compute icing risk
                    ambient_temp = telemetry_row.get("ambient_temp_c", 15)
                    humidity = telemetry_row.get("humidity_pct", 50)
                    icing_advisory = self.env_physics.classify_icing_risk(ambient_temp, humidity)

                    # Compute corrosion index
                    maritime_hours = telemetry_row.get("maritime_hours_cumulative", 0)
                    airframe_id = flight_info.get("airframe_id", config.DEFAULT_AIRFRAME_ID)
                    corrosion_index = self.env_physics.update_corrosion_index(
                        airframe_id, maritime_hours
                    )
                    corrosion_advisory = self.env_physics.get_corrosion_advisory(corrosion_index)

                    # Attribute fault
                    fault_parameter = flight_info.get("fault_injected")
                    fault_category = None
                    if fault_parameter:
                        param_eval = next(
                            (e for e in evaluations if e["parameter"] == fault_parameter), None
                        )
                        if param_eval:
                            fault_category = self.env_physics.attribute_fault_with_icing_override(
                                fault_parameter=fault_parameter,
                                fault_status=param_eval["status"],
                                icing_risk=icing_advisory,
                                fuel_flow_deviation=next(
                                    (e["deviation_pct"] for e in evaluations if e["parameter"] == "fuel_flow_lph"),
                                    0,
                                ),
                                rpm=telemetry_row.get("rpm", 2000),
                                egt_deviation=next(
                                    (e["deviation_pct"] for e in evaluations if e["parameter"] == "egt_c"), 0
                                ),
                            )

                    # Compute flight condition
                    parameter_statuses = {e["parameter"]: e["status"] for e in evaluations}
                    subsys_health = self.compute_subsystem_health(parameter_statuses)
                    overall_status = self.compute_overall_status(subsys_health)

                    cursor.execute(
                        """
                        INSERT INTO flight_condition (
                            flight_id, mission_time_s, timestamp,
                            subsystem_health_json, overall_status, icing_advisory, fault_category
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(flight_id, mission_time_s) DO UPDATE SET
                            timestamp = excluded.timestamp,
                            subsystem_health_json = excluded.subsystem_health_json,
                            overall_status = excluded.overall_status,
                            icing_advisory = excluded.icing_advisory,
                            fault_category = excluded.fault_category
                    """,
                        (
                            self.flight_id,
                            telemetry_row["mission_time_s"],
                            telemetry_row["timestamp"],
                            json.dumps(subsys_health),
                            overall_status,
                            icing_advisory,
                            fault_category,
                        ),
                    )

                    self.last_processed_time_s = telemetry_row["mission_time_s"]

                    print(
                        f"[{self.flight_id}] Time: {telemetry_row['mission_time_s']/60:5.1f} min | "
                        f"Overall: {overall_status:8s} | Icing: {icing_advisory:8s} | "
                        f"Health: {subsys_health}"
                    )

                conn.commit()

        except KeyboardInterrupt:
            print("\nLive polling stopped by user")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Physics layer: evaluate telemetry and produce health status."
    )
    parser.add_argument("--flight-id", required=True, help="Flight identifier")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live mode: poll for new telemetry (default: replay mode)",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Replay mode: process complete flight (default)",
    )

    args = parser.parse_args()

    # Determine mode (live if --live, else replay)
    is_live = args.live and not args.replay

    # Run evaluator
    evaluator = PhysicsEvaluator(flight_id=args.flight_id, is_live=is_live)
    evaluator.process_flight()


if __name__ == "__main__":
    main()
