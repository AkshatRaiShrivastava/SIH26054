"""
Database schema initialization and utilities for the Digital Twin Pipeline.
"""

import sqlite3
import os
from pathlib import Path

# Import config from sibling package
from ..utils.config import DATABASE_PATH



def init_database():
    """Initialize the SQLite database with required schemas."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Flights table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            flight_id TEXT PRIMARY KEY,
            start_time TEXT,
            climate_zone TEXT,
            seed INTEGER,
            fault_injected TEXT,        -- NULL, or e.g. "oil_pressure_psi"
            status TEXT,                -- 'in_progress' | 'complete'
            airframe_id TEXT            -- persistent aircraft identifier
        );
    """)

    # Telemetry table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            flight_id TEXT,
            mission_time_s REAL,
            timestamp TEXT,
            phase TEXT,
            -- engine channels
            rpm REAL,
            cht_c REAL,
            egt_c REAL,
            oil_temp_c REAL,
            oil_pressure_psi REAL,
            fuel_flow_lph REAL,
            vibration_g REAL,
            battery_v REAL,
            afr REAL,
            altitude_m REAL,
            ambient_temp_c REAL,
            -- environmental channels (added in step 3)
            humidity_pct REAL,
            pressure_altitude_m REAL,
            precipitation INTEGER,
            hours_since_filter_service REAL,
            maritime_hours_cumulative REAL,
            climate_zone TEXT,
            FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
        );
    """)

    # Evaluations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            flight_id TEXT,
            mission_time_s REAL,
            timestamp TEXT,
            parameter TEXT,
            actual REAL,
            expected REAL,
            deviation_pct REAL,
            raw_status TEXT,          -- per-packet, undebounced
            status TEXT,              -- debounced, dashboard-facing
            FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
        );
    """)

    # Flight condition table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flight_condition (
            flight_id TEXT,
            mission_time_s REAL,
            timestamp TEXT,
            subsystem_health_json TEXT,
            overall_status TEXT,
            icing_advisory TEXT,
            fault_category TEXT,
            PRIMARY KEY (flight_id, mission_time_s),
            FOREIGN KEY (flight_id) REFERENCES flights(flight_id)
        );
    """)

    # Corrosion tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corrosion_tracking (
            airframe_id TEXT PRIMARY KEY,
            corrosion_index REAL,
            last_updated TEXT
        );
    """)

    conn.commit()
    conn.close()


def get_connection():
    """Get a database connection."""
    return sqlite3.connect(DATABASE_PATH)


def close_connection(conn):
    """Close a database connection."""
    if conn:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")
