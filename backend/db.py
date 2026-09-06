import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://uav:password@localhost:5432/uav_engine")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS mission_runs (mission_id TEXT PRIMARY KEY, started_at TIMESTAMPTZ DEFAULT NOW(), ended_at TIMESTAMPTZ, scenario TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running', total_elapsed_s REAL DEFAULT 0, current_phase_id INTEGER DEFAULT 0, speed_multiplier REAL DEFAULT 1.0);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS raw_telemetry (id SERIAL PRIMARY KEY, mission_id TEXT NOT NULL, timestamp TIMESTAMPTZ DEFAULT NOW(), elapsed_s REAL NOT NULL, phase_id INTEGER NOT NULL, rpm DOUBLE PRECISION, cht_c DOUBLE PRECISION, egt_c DOUBLE PRECISION, oil_pressure_kpa DOUBLE PRECISION, oil_temperature_c DOUBLE PRECISION, fuel_flow_lph DOUBLE PRECISION, vibration_mms DOUBLE PRECISION, afr DOUBLE PRECISION, battery_voltage DOUBLE PRECISION, altitude_m DOUBLE PRECISION, ambient_temp_c DOUBLE PRECISION);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS computed_metrics (id SERIAL PRIMARY KEY, mission_id TEXT NOT NULL, timestamp TIMESTAMPTZ DEFAULT NOW(), elapsed_s REAL NOT NULL, phase_id INTEGER NOT NULL, cht_expected DOUBLE PRECISION, cht_deviation_pct DOUBLE PRECISION, egt_expected DOUBLE PRECISION, egt_deviation_pct DOUBLE PRECISION, oil_pressure_expected DOUBLE PRECISION, oil_pressure_deviation_pct DOUBLE PRECISION, oil_temp_expected DOUBLE PRECISION, oil_temp_deviation_pct DOUBLE PRECISION, fuel_flow_expected DOUBLE PRECISION, fuel_flow_deviation_pct DOUBLE PRECISION, vibration_baseline DOUBLE PRECISION, vibration_deviation_pct DOUBLE PRECISION, anomaly_score DOUBLE PRECISION, is_anomaly BOOLEAN, model_version TEXT, health_index DOUBLE PRECISION);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS fault_events (id SERIAL PRIMARY KEY, mission_id TEXT NOT NULL, timestamp TIMESTAMPTZ DEFAULT NOW(), elapsed_s REAL NOT NULL, fault_category TEXT NOT NULL, confidence TEXT NOT NULL, driving_features TEXT[]);"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS rul_predictions (id SERIAL PRIMARY KEY, mission_id TEXT NOT NULL, timestamp TIMESTAMPTZ DEFAULT NOW(), elapsed_s REAL NOT NULL, predicted_rul_minutes DOUBLE PRECISION, confidence_band_minutes DOUBLE PRECISION, driving_channel TEXT, model_version TEXT);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_raw_telemetry_mission_time ON raw_telemetry (mission_id, elapsed_s);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_computed_mission_time ON computed_metrics (mission_id, elapsed_s);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fault_mission_time ON fault_events (mission_id, elapsed_s);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rul_mission_time ON rul_predictions (mission_id, elapsed_s);"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
