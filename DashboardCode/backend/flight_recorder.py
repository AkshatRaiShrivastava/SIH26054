"""PostgreSQL persistence for complete CAN telemetry samples grouped into flights."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
import psycopg

from .models import EngineTelemetry
from .telemetry_state import SIGNAL_NAMES


class FlightRecorder:
    """Records one backend session as one flight without persisting partial frames."""

    def __init__(self, database_url: str, interface: str, label: str = "unknown") -> None:
        self.database_url = database_url
        self.interface = interface
        self.label = label
        self.flight_id = f"FL-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        self._started_at = datetime.now(timezone.utc)
        self._started_monotonic = time.monotonic()
        self._observed_signals: set[str] = set()
        self._sample_index = 0
        self._lock = threading.Lock()
        self._connection = psycopg.connect(database_url)
        self._create_schema()
        self._connection.execute(
            "INSERT INTO flights (flight_id, started_at, status, source_interface, label) VALUES (%s, %s, 'in_progress', %s, %s)",
            (self.flight_id, self._started_at.isoformat(), interface, label),
        )
        self._connection.commit()

    def _create_schema(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS flights (
                flight_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL,
                source_interface TEXT NOT NULL,
                label TEXT NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0
            );
            """,
            """CREATE TABLE IF NOT EXISTS flight_telemetry (
                flight_id TEXT NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                sample_index INTEGER NOT NULL,
                timestamp_utc TEXT NOT NULL,
                mission_time_s REAL NOT NULL,
                rpm REAL NOT NULL,
                cht_c REAL NOT NULL,
                egt_c REAL NOT NULL,
                oil_pressure_kpa REAL NOT NULL,
                oil_temperature_c REAL NOT NULL,
                fuel_flow_lph REAL NOT NULL,
                vibration_mms REAL NOT NULL,
                battery_voltage REAL NOT NULL,
                PRIMARY KEY (flight_id, sample_index)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_flight_telemetry_time ON flight_telemetry (flight_id, mission_time_s)",
        )
        for statement in statements:
            self._connection.execute(statement)
        self._connection.commit()

    def record_signal(self, signal_name: str, snapshot: EngineTelemetry) -> bool:
        """Save a row only after every CAN signal has arrived at least once."""
        with self._lock:
            self._observed_signals.add(signal_name)
            if not set(SIGNAL_NAMES).issubset(self._observed_signals):
                return False
            self._observed_signals.clear()
            self._record_snapshot(snapshot)
            return True

    def record_snapshot(self, snapshot: EngineTelemetry) -> None:
        """Save a full snapshot directly; used by offline dataset generators."""
        with self._lock:
            self._record_snapshot(snapshot)

    def _record_snapshot(self, snapshot: EngineTelemetry) -> None:
        mission_time_s = time.monotonic() - self._started_monotonic
        self._connection.execute(
            """INSERT INTO flight_telemetry VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (self.flight_id, self._sample_index, snapshot.timestamp, mission_time_s,
             snapshot.rpm, snapshot.cht, snapshot.egt, snapshot.oil_pressure,
             snapshot.oil_temperature, snapshot.fuel_flow, snapshot.vibration, snapshot.battery_voltage),
        )
        self._sample_index += 1
        self._connection.execute("UPDATE flights SET sample_count = %s WHERE flight_id = %s", (self._sample_index, self.flight_id))
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            self._connection.execute(
                "UPDATE flights SET ended_at = %s, status = 'complete', sample_count = %s WHERE flight_id = %s",
                (datetime.now(timezone.utc).isoformat(), self._sample_index, self.flight_id),
            )
            self._connection.commit()
            self._connection.close()
            self._connection = None
