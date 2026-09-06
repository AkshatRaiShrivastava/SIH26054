"""PostgreSQL persistence for complete CAN telemetry samples grouped into flights."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Optional
from datetime import datetime, timezone
import psycopg2

from .models import EngineTelemetry
from .telemetry_state import SIGNAL_NAMES


class FlightRecorder:
    """PostgreSQL persistence for complete CAN telemetry samples grouped into flights."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.flight_id: Optional[str] = None
        self.interface: Optional[str] = None
        self.label: Optional[str] = None
        self._started_at: Optional[datetime] = None
        self._started_monotonic: Optional[float] = None
        self._observed_signals: set[str] = set()
        self._sample_index = 0
        self._lock = threading.Lock()
        self._connection = psycopg2.connect(database_url)
        self._connection.autocommit = True
        self._create_schema()

    def _execute(self, query: str, params: tuple = ()) -> None:
        with self._connection.cursor() as cur:
            cur.execute(query, params)

    def start_flight(self, flight_id: str, interface: str, label: str = "unknown") -> None:
        """Explicitly start a new flight session."""
        with self._lock:
            self.flight_id = flight_id
            self.interface = interface
            self.label = label
            self._started_at = datetime.now(timezone.utc)
            self._started_monotonic = time.monotonic()
            self._observed_signals.clear()
            self._sample_index = 0

            self._execute(
                """
                INSERT INTO flights (flight_id, started_at, status, source_interface, label)
                VALUES (%s, %s, 'RUNNING', %s, %s)
                ON CONFLICT (flight_id) DO UPDATE SET status = 'RUNNING', started_at = EXCLUDED.started_at
                """,
                (self.flight_id, self._started_at.isoformat(), interface, label),
            )
            print(f"Flight {self.flight_id} started.")

    def record_physics_result(
        self,
        flight_id: str,
        timestamp: str,
        signal_name: str,
        actual: float,
        expected: float,
        residual: float,
        residual_pct: float,
        status: str = "normal",
        mission_time_s: float = 0.0,
    ) -> None:
        """Persist a physics evaluation result."""
        with self._lock:
            if not self.flight_id:
                return
            try:
                self._execute(
                    """
                    INSERT INTO physics_results (flight_id, timestamp, mission_time_s, signal_name, actual_value, expected_value, residual, residual_pct, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (flight_id, timestamp, mission_time_s, signal_name, actual, expected, residual, residual_pct, status),
                )
            except Exception as e:
                print(f"Error persisting physics result: {e}")

    def record_maintenance_recommendation(
        self,
        flight_id: str,
        component: str,
        recommendation: str,
        priority: str,
        reason: str,
        evidence: str,
        due_hours: Optional[float] = None,
    ) -> None:
        """Persist a maintenance recommendation."""
        with self._lock:
            if not self.flight_id:
                return
            try:
                self._execute(
                    """
                    INSERT INTO maintenance_records (flight_id, component, recommendation, priority, reason, evidence, due_hours, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', %s)
                    """,
                    (
                        flight_id,
                        component,
                        recommendation,
                        priority,
                        reason,
                        evidence,
                        due_hours,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except Exception as e:
                print(f"Error persisting maintenance record: {e}")

    def stop_flight(self, status: str = "COMPLETED") -> None:
        """Finalize the current flight session."""
        with self._lock:
            if not self.flight_id:
                return

            self._execute(
                """
                UPDATE flights SET ended_at = %s, status = %s, sample_count = %s WHERE flight_id = %s
                """,
                (datetime.now(timezone.utc).isoformat(), status, self._sample_index, self.flight_id),
            )
            print(f"Flight {self.flight_id} status set to {status}.")
            self.flight_id = None

    def _create_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS flights (
                flight_id TEXT PRIMARY KEY,
                created_at TEXT,
                started_at TEXT,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'CREATED',
                source_interface TEXT NOT NULL DEFAULT 'vcan0',
                label TEXT NOT NULL DEFAULT 'flight',
                sample_count INTEGER NOT NULL DEFAULT 0,
                mission_type TEXT DEFAULT 'surveillance',
                notes TEXT
            );
            """,
            """CREATE TABLE IF NOT EXISTS telemetry (
                id SERIAL PRIMARY KEY,
                flight_id TEXT NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                sample_index INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                mission_time_s REAL NOT NULL,
                phase TEXT DEFAULT 'cruise',
                mission_stage TEXT DEFAULT 'cruise',
                rpm REAL NOT NULL,
                cht_c REAL NOT NULL,
                egt_c REAL NOT NULL,
                oil_pressure_kpa REAL NOT NULL,
                oil_pressure_psi REAL,
                oil_temperature_c REAL NOT NULL,
                fuel_flow_lph REAL NOT NULL,
                vibration_mms REAL NOT NULL,
                vibration_g REAL,
                battery_voltage REAL NOT NULL,
                altitude_m REAL DEFAULT 0,
                ambient_temp_c REAL DEFAULT 15,
                throttle REAL DEFAULT 0,
                engine_load REAL DEFAULT 0
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (flight_id, mission_time_s)",
            """
            CREATE TABLE IF NOT EXISTS physics_results (
                id SERIAL PRIMARY KEY,
                flight_id TEXT NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                mission_time_s REAL DEFAULT 0,
                signal_name TEXT NOT NULL,
                actual_value REAL NOT NULL,
                expected_value REAL NOT NULL,
                residual REAL NOT NULL,
                residual_pct REAL NOT NULL,
                status TEXT DEFAULT 'normal'
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS health_predictions (
                id SERIAL PRIMARY KEY,
                flight_id TEXT NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                engine_health REAL NOT NULL,
                anomaly_score REAL NOT NULL,
                fault_type TEXT,
                confidence REAL NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS fault_events (
                id SERIAL PRIMARY KEY,
                flight_id TEXT NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                fault_type TEXT NOT NULL,
                severity REAL NOT NULL,
                status TEXT NOT NULL,
                description TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS maintenance_records (
                id SERIAL PRIMARY KEY,
                flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
                component TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                priority TEXT NOT NULL,
                reason TEXT,
                evidence TEXT,
                due_hours REAL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            """,
        )
        for statement in statements:
            try:
                self._execute(statement)
            except Exception as e:
                print(f"Schema execution notice: {e}")

    def record_signal(self, signal_name: str, snapshot: EngineTelemetry) -> bool:
        """Save a row only after every CAN signal has arrived at least once."""
        with self._lock:
            if not self.flight_id:
                return False
            self._observed_signals.add(signal_name)
            if not set(SIGNAL_NAMES).issubset(self._observed_signals):
                return False
            self._observed_signals.clear()
            self._record_snapshot(snapshot)
            return True

    def record_snapshot(self, snapshot: EngineTelemetry) -> None:
        """Save a full snapshot directly; used by offline dataset generators."""
        with self._lock:
            if not self.flight_id:
                return
            self._record_snapshot(snapshot)

    def _record_snapshot(self, snapshot: EngineTelemetry) -> None:
        if not self.flight_id:
            return
        mission_time_s = time.monotonic() - (self._started_monotonic or time.monotonic())
        oil_p_psi = snapshot.oil_pressure * 0.145038
        vib_g = snapshot.vibration / 9.81
        stage_map = {
            0: "OFF", 1: "PRE_FLIGHT", 2: "ENGINE_START", 3: "WARMUP",
            4: "TAXI", 5: "TAKEOFF", 6: "INITIAL_CLIMB", 7: "CLIMB",
            8: "CRUISE_CLIMB", 9: "CRUISE", 10: "HIGH_ALTITUDE_CRUISE",
            11: "LOITER", 12: "DESCENT", 13: "APPROACH", 14: "LANDING",
            15: "COOLDOWN", 16: "SHUTDOWN", 17: "POST_FLIGHT", 18: "MISSION_COMPLETE",
            99: "THROTTLE_TRANSITION"
        }
        current_phase = stage_map.get(int(snapshot.mission_stage), "UNKNOWN")
        self._execute(
            """INSERT INTO telemetry (
                flight_id, sample_index, timestamp, mission_time_s, phase, mission_stage,
                rpm, cht_c, egt_c, oil_pressure_kpa, oil_pressure_psi, oil_temperature_c,
                fuel_flow_lph, vibration_mms, vibration_g, battery_voltage,
                altitude_m, throttle, engine_load
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                self.flight_id,
                self._sample_index,
                snapshot.timestamp,
                mission_time_s,
                current_phase,
                current_phase,
                snapshot.rpm,
                snapshot.cht,
                snapshot.egt,
                snapshot.oil_pressure,
                oil_p_psi,
                snapshot.oil_temperature,
                snapshot.fuel_flow,
                snapshot.vibration,
                vib_g,
                snapshot.battery_voltage,
                snapshot.altitude,
                snapshot.throttle,
                snapshot.load,
            ),
        )
        self._sample_index += 1
        self._execute("UPDATE flights SET sample_count = %s WHERE flight_id = %s", (self._sample_index, self.flight_id))

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            if self.flight_id:
                self._execute(
                    "UPDATE flights SET ended_at = %s, status = 'COMPLETED', sample_count = %s WHERE flight_id = %s",
                    (datetime.now(timezone.utc).isoformat(), self._sample_index, self.flight_id),
                )
            self._connection.close()
            self._connection = None
