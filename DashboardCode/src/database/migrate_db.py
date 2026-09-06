import psycopg2
from src.database.database import get_connection, close_connection

def migrate():
    print("Checking database schema for migrations...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # Map of table name to expected columns
    expected_schema = {
        "flights": {
            "flight_id": "TEXT",
            "start_time": "TIMESTAMP",
            "climate_zone": "TEXT",
            "seed": "INTEGER",
            "fault_injected": "TEXT",
            "status": "TEXT",
            "airframe_id": "TEXT"
        },
        "telemetry": {
            "id": "SERIAL",
            "flight_id": "TEXT",
            "mission_time_s": "DOUBLE PRECISION",
            "timestamp": "TIMESTAMP",
            "phase": "TEXT",
            "rpm": "DOUBLE PRECISION",
            "cht_c": "DOUBLE PRECISION",
            "egt_c": "DOUBLE PRECISION",
            "oil_temp_c": "DOUBLE PRECISION",
            "oil_pressure_psi": "DOUBLE PRECISION",
            "fuel_flow_lph": "DOUBLE PRECISION",
            "vibration_g": "DOUBLE PRECISION",
            "battery_v": "DOUBLE PRECISION",
            "afr": "DOUBLE PRECISION",
            "altitude_m": "DOUBLE PRECISION",
            "ambient_temp_c": "DOUBLE PRECISION",
            "humidity_pct": "DOUBLE PRECISION",
            "pressure_altitude_m": "DOUBLE PRECISION",
            "precipitation": "INTEGER",
            "hours_since_filter_service": "DOUBLE PRECISION",
            "maritime_hours_cumulative": "DOUBLE PRECISION",
            "climate_zone": "TEXT"
        }
    }

    try:
        for table, columns in expected_schema.items():
            print(f"Checking table: {table}")
            cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table}';
            """)
            existing_cols = [row[0] for row in cur.fetchall()]

            for col_name, col_type in columns.items():
                if col_name not in existing_cols:
                    print(f"  Adding missing column {col_name} ({col_type}) to {table}...")
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};")

        print("Database schema sync complete.")

    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        close_connection(conn)

if __name__ == "__main__":
    migrate()
