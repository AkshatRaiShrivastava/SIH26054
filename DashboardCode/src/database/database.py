import psycopg2
from psycopg2 import sql
import os
from typing import Any

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "uav_telemetry")
DB_USER = os.getenv("DB_USER", "uav")
DB_PASS = os.getenv("DB_PASS", "uav")
DB_PASS = os.getenv("DB_PASS", "uav_password_123")

class Database:
    """Singleton for managing DB connections."""
    def __init__(self):
        self.conn = None

    def get_connection(self):
        """Get a PostgreSQL database connection."""
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )

    def close_connection(self, conn):
        """Close a database connection."""
        if conn:
            conn.close()

database = Database()

def get_connection():
    """Wrapper for compatibility."""
    return database.get_connection()

def close_connection(conn):
    """Wrapper for compatibility."""
    return database.close_connection(conn)

def init_database():
    """Initialize the PostgreSQL database with required Digital Twin schemas."""
    conn = get_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. Flights table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            flight_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'CREATED', -- 'CREATED' | 'ARMED' | 'RUNNING' | 'COMPLETED' | 'ABORTED'
            mission_type TEXT DEFAULT 'surveillance',
            notes TEXT,
            sample_count INTEGER NOT NULL DEFAULT 0,
            source_interface TEXT DEFAULT 'vcan0',
            label TEXT DEFAULT 'flight',
            climate_zone TEXT,
            seed INTEGER,
            fault_injected TEXT,
            airframe_id TEXT DEFAULT 'UAV-ENGINE-01'
        );
    """)

    # 2. Telemetry table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id SERIAL PRIMARY KEY,
            flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
            sample_index INTEGER DEFAULT 0,
            mission_time_s DOUBLE PRECISION,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            phase TEXT DEFAULT 'cruise',
            mission_stage TEXT DEFAULT 'cruise',
            rpm DOUBLE PRECISION,
            cht_c DOUBLE PRECISION,
            egt_c DOUBLE PRECISION,
            oil_temp_c DOUBLE PRECISION,
            oil_pressure_psi DOUBLE PRECISION,
            oil_pressure_kpa DOUBLE PRECISION,
            fuel_flow_lph DOUBLE PRECISION,
            vibration_g DOUBLE PRECISION,
            vibration_mms DOUBLE PRECISION,
            battery_v DOUBLE PRECISION,
            afr DOUBLE PRECISION,
            altitude_m DOUBLE PRECISION,
            ambient_temp_c DOUBLE PRECISION,
            throttle DOUBLE PRECISION,
            engine_load DOUBLE PRECISION,
            humidity_pct DOUBLE PRECISION,
            pressure_altitude_m DOUBLE PRECISION,
            precipitation INTEGER,
            hours_since_filter_service DOUBLE PRECISION,
            maritime_hours_cumulative DOUBLE PRECISION,
            climate_zone TEXT
        );
    """)

    # 3. Physics Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS physics_results (
            id SERIAL PRIMARY KEY,
            flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mission_time_s DOUBLE PRECISION,
            signal_name TEXT NOT NULL,
            actual_value DOUBLE PRECISION NOT NULL,
            expected_value DOUBLE PRECISION NOT NULL,
            residual DOUBLE PRECISION NOT NULL,
            residual_pct DOUBLE PRECISION NOT NULL,
            status TEXT DEFAULT 'normal'
        );
    """)

    # 4. Health Predictions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_predictions (
            id SERIAL PRIMARY KEY,
            flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            engine_health DOUBLE PRECISION DEFAULT 100.0,
            anomaly_score DOUBLE PRECISION DEFAULT 0.0,
            fault_type TEXT,
            fault_probability DOUBLE PRECISION DEFAULT 0.0,
            degradation_score DOUBLE PRECISION DEFAULT 0.0,
            rul_hours DOUBLE PRECISION,
            confidence DOUBLE PRECISION DEFAULT 1.0
        );
    """)

    # 5. Fault Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fault_events (
            id SERIAL PRIMARY KEY,
            flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fault_type TEXT NOT NULL,
            severity DOUBLE PRECISION NOT NULL,
            status TEXT NOT NULL,
            description TEXT
        );
    """)

    # 6. Maintenance Records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id SERIAL PRIMARY KEY,
            flight_id TEXT REFERENCES flights(flight_id) ON DELETE CASCADE,
            component TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            priority TEXT NOT NULL,
            due_hours DOUBLE PRECISION,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            reason TEXT,
            evidence TEXT
        );
    """)

    # Indexes for rapid time-series retrieval
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_flight_time ON telemetry (flight_id, timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_flight_mission ON telemetry (flight_id, mission_time_s);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_physics_flight_time ON physics_results (flight_id, timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_flight_time ON health_predictions (flight_id, timestamp);")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        init_database()
        print("PostgreSQL database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
