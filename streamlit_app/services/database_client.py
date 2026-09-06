"""
PostgreSQL database helper for Streamlit Admin Console.
"""

import os
import psycopg2
from typing import List, Dict, Any, Optional

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "uav_telemetry")
DB_USER = os.getenv("DB_USER", "uav")
DB_PASS = os.getenv("DB_PASS", "uav")
DB_PASS = os.getenv("DB_PASS", "uav_password_123")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=3,
    )


def fetch_all_flights() -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT flight_id, created_at, started_at, ended_at, status, mission_type, label, sample_count FROM flights ORDER BY created_at DESC, started_at DESC;")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def fetch_telemetry_for_flight(flight_id: str) -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM telemetry WHERE flight_id = %s ORDER BY mission_time_s ASC;", (flight_id,))
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []


def fetch_physics_for_flight(flight_id: str) -> List[Dict[str, Any]]:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM physics_results WHERE flight_id = %s ORDER BY mission_time_s ASC;", (flight_id,))
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            conn.close()
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []
