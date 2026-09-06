"""FastAPI application for the telemetry backend."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
import subprocess
import docker
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import psycopg

from backend.models import HealthSnapshot, TelemetryMessage
from backend.flight_recorder import FlightRecorder
from backend.telemetry_service import TelemetryService
from backend.websocket import TelemetryBroadcaster, websocket_telemetry_endpoint

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MAPPING = BASE_DIR / "config" / "can_mapping.yaml"

async def wait_for_db(database_url: str, retries: int = 10, delay: float = 2.0):
    """Wait for PostgreSQL to become available."""
    import logging
    logger = logging.getLogger("backend")
    for i in range(retries):
        try:
            # Attempt a simple connection
            with psycopg.connect(database_url) as conn:
                logger.info("Database connection established.")
                return True
        except Exception as e:
            logger.warning(f"Database not ready (attempt {i+1}/{retries}): {e}")
            await asyncio.sleep(delay)
    logger.error("Database connection failed after maximum retries.")
    return False

def create_app(interface: str, mapping_path: Path, database_url: str) -> FastAPI:
    broadcaster = TelemetryBroadcaster()
    recorder = FlightRecorder(database_url)
    service = TelemetryService(interface=interface, mapping_path=mapping_path, recorder=recorder)

    docker_client = docker.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Ensure DB is ready
        if not await wait_for_db(database_url):
            # We don't exit here to allow the app to start and show "DISCONNECTED"
            # but we log the error.
            pass

        service.start()
        broadcast_task = asyncio.create_task(_broadcast_loop(service, broadcaster, recorder))
        app.state.telemetry_service = service
        app.state.broadcaster = broadcaster
        app.state.flight_recorder = recorder
        try:
            yield
        finally:
            broadcast_task.cancel()
            service.stop()
            recorder.close()

    app = FastAPI(title="UAV Engine Telemetry Backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthSnapshot)
    async def health() -> HealthSnapshot:
        health_state = service.state.health()
        return HealthSnapshot(
            ok=True,
            can_interface=health_state.can_interface,
            backend="running",
            message="Telemetry backend is ready",
        )

    @app.get("/api/telemetry/latest", response_model=TelemetryMessage)
    async def latest() -> TelemetryMessage:
        snapshot = service.state.snapshot()
        if snapshot is None:
            return TelemetryMessage(
                timestamp="",
                rpm=0,
                cht=0.0,
                egt=0.0,
                oil_pressure=0.0,
                oil_temperature=0.0,
                fuel_flow=0.0,
                vibration=0.0,
                battery_voltage=0.0,
                source_interface=interface,
                sequence=0,
            )
        return TelemetryMessage(**snapshot.model_dump())

    @app.get("/api/data-health")
    async def data_health():
        return service.state.health().model_dump(mode="json")

    # --- FLIGHT SESSION MANAGEMENT ---

    @app.get("/api/flights")
    async def flights():
        try:
            with psycopg.connect(recorder.database_url) as connection:
                rows = connection.execute("SELECT * FROM flights ORDER BY started_at DESC").fetchall()
                columns = [column[0] for column in connection.execute("SELECT * FROM flights LIMIT 0").description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/flights")
    async def create_flight(label: str = "flight", mission_type: str = "surveillance", notes: str = ""):
        flight_id = f"FLT-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:4].upper()}"
        try:
            with psycopg.connect(recorder.database_url) as connection:
                created_at = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """INSERT INTO flights (flight_id, created_at, status, source_interface, label, mission_type, notes)
                       VALUES (%s, %s, 'CREATED', %s, %s, %s, %s)""",
                    (flight_id, created_at, recorder.interface or interface, label, mission_type, notes),
                )
                connection.commit()
                return {"flight_id": flight_id, "status": "CREATED", "created_at": created_at}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/flights/{flight_id}")
    async def get_flight(flight_id: str):
        try:
            with psycopg.connect(recorder.database_url) as connection:
                cursor = connection.execute("SELECT * FROM flights WHERE flight_id = %s", (flight_id,))
                row = cursor.fetchone()
                if not row:
                    return {"error": "Flight not found"}
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/flights/{flight_id}/start")
    async def start_flight(flight_id: str):
        recorder.start_flight(
            flight_id=flight_id,
            interface=service.interface,
            label=recorder.label or "active_flight",
        )
        return {"status": "RUNNING", "flight_id": flight_id}

    @app.post("/api/flights/{flight_id}/stop")
    async def stop_flight(flight_id: str):
        recorder.stop_flight(status="COMPLETED")
        return {"status": "COMPLETED", "flight_id": flight_id}

    @app.post("/api/flights/{flight_id}/abort")
    async def abort_flight(flight_id: str):
        recorder.stop_flight(status="ABORTED")
        return {"status": "ABORTED", "flight_id": flight_id}

    # --- FLIGHT HISTORICAL DATA API ---

    @app.get("/api/live/physics")
    async def live_physics():
        return service.latest_physics_results

    @app.get("/api/live/maintenance")
    async def live_maintenance():
        return service.latest_maintenance_records

    @app.get("/api/flights/{flight_id}/telemetry")
    async def flight_telemetry(flight_id: str, limit: int = 2000):
        try:
            with psycopg.connect(recorder.database_url) as connection:
                cursor = connection.execute(
                    "SELECT * FROM flight_telemetry WHERE flight_id = %s ORDER BY mission_time_s ASC LIMIT %s",
                    (flight_id, limit),
                )
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/flights/{flight_id}/physics")
    async def flight_physics(flight_id: str, limit: int = 2000):
        try:
            with psycopg.connect(recorder.database_url) as connection:
                cursor = connection.execute(
                    "SELECT * FROM physics_results WHERE flight_id = %s ORDER BY mission_time_s ASC LIMIT %s",
                    (flight_id, limit),
                )
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/flights/{flight_id}/maintenance")
    async def flight_maintenance(flight_id: str):
        try:
            with psycopg.connect(recorder.database_url) as connection:
                cursor = connection.execute(
                    "SELECT * FROM maintenance_records WHERE flight_id = %s",
                    (flight_id,),
                )
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/flights/{flight_id}/health")
    async def flight_health(flight_id: str):
        try:
            with psycopg.connect(recorder.database_url) as connection:
                cursor = connection.execute(
                    "SELECT * FROM health_predictions WHERE flight_id = %s ORDER BY timestamp DESC",
                    (flight_id,),
                )
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return {"error": str(e)}

    # --- LIVE DATA & SUBSYSTEM STATUS ---

    @app.get("/api/live/status")
    async def live_status():
        connection_ok = False
        try:
            with psycopg.connect(recorder.database_url) as conn:
                connection_ok = True
        except Exception:
            connection_ok = False

        data_health = service.state.health()
        can_ok = data_health.can_interface in ["ok", "active", "online"] or data_health.total_frames > 0

        active_flight = recorder.flight_id
        flight_status = "IDLE"
        if active_flight:
            flight_status = "RUNNING"

        return {
            "can": "CONNECTED" if can_ok else "DISCONNECTED",
            "backend": "ONLINE",
            "postgresql": "CONNECTED" if connection_ok else "DISCONNECTED",
            "physics_engine": "RUNNING",
            "ai_engine": "READY",
            "active_flight": active_flight or "NONE",
            "flight_status": flight_status,
            "total_frames_received": data_health.total_frames,
            "stale_telemetry": data_health.stale,
        }

    @app.get("/api/live/telemetry")
    async def live_telemetry():
        snapshot = service.state.snapshot()
        if snapshot is None:
            return {}
        return snapshot.model_dump()

    @app.get("/api/live/physics")
    async def live_physics():
        return service.latest_physics_results

    @app.get("/api/live/health")
    async def live_health():
        physics_res = service.latest_physics_results
        max_residual = 0.0
        for sig, val in physics_res.items():
            res_pct = abs(val.get("residual_pct", 0.0))
            if res_pct > max_residual:
                max_residual = res_pct

        anomaly_score = min(100.0, max_residual * 2.0)
        engine_health = max(0.0, 100.0 - anomaly_score)

        return {
            "engine_health": round(engine_health, 1),
            "anomaly_score": round(anomaly_score, 1),
            "current_fault": "NONE" if anomaly_score < 30.0 else "PHYSICS DEVIATION DETECTED",
            "rul": "Not available (Model not active)",
            "model_status": "Model not active",
        }

    @app.get("/api/live/maintenance")
    async def live_maintenance():
        recs = service.latest_maintenance_records
        return [
            {
                "component": r.component,
                "priority": r.priority,
                "reason": r.reason,
                "evidence": r.evidence,
                "recommendation": r.recommendation,
                "status": r.status,
                "due_hours": r.due_hours,
                "created_at": r.created_at,
            }
            for r in recs
        ]

    # --- SIMULATOR CONTROLS (DOCKER VERSION) ---

    @app.post("/api/simulator/start")
    async def start_simulator(mission: str = "surveillance", speed: float = 1.0, fault: str = ""):
        try:
            container = docker_client.containers.get("uav-simulator")
            if container.status == "running":
                return {"status": "ALREADY_RUNNING", "id": container.id}

            # To change the mission/fault, we need to restart the container with a new command.
            # However, the simulator uses CLI args. In Docker, we can override the command.

            cmd = ["python", "main.py", "--mission", mission, "--speed", str(speed), "--interface", interface]
            if fault:
                cmd.extend(["--fault", fault])

            # Re-create the container with the new command to apply mission/fault settings
            container.stop()
            container.remove()

            docker_client.containers.run(
                "uav-simulator",
                name="uav-simulator",
                command=cmd,
                network_mode="host",
                detach=True,
                volumes={os.path.abspath("uav-engine-digital-twin"): {"bind": "/app", "mode": "rw"}},
                environment={"CAN_INTERFACE": interface}
            )

            return {"status": "STARTED", "mission": mission, "speed": speed}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    @app.post("/api/simulator/stop")
    async def stop_simulator():
        try:
            container = docker_client.containers.get("uav-simulator")
            if container.status == "running":
                container.stop()
                return {"status": "STOPPED"}
            return {"status": "NOT_RUNNING"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    @app.get("/api/simulator/status")
    async def simulator_status():
        try:
            container = docker_client.containers.get("uav-simulator")
            return {"running": container.status == "running", "id": container.id}
        except Exception:
            return {"running": False, "id": None}

    # --- WEBSOCKET BROADCAST ---

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket):
        await websocket_telemetry_endpoint(websocket, broadcaster)

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(websocket: WebSocket):
        await websocket_telemetry_endpoint(websocket, broadcaster)

    return app


async def _broadcast_loop(service: TelemetryService, broadcaster: TelemetryBroadcaster, recorder: FlightRecorder) -> None:
    while True:
        snapshot = service.state.snapshot()
        if snapshot is not None:
            payload = {
                "flight_id": recorder.flight_id or "NONE",
                "telemetry": snapshot.model_dump(mode="json"),
                "physics": service.latest_physics_results,
                "maintenance": [
                    rec.__dict__ if not hasattr(rec, "model_dump") else rec.model_dump(mode="json")
                    for rec in service.latest_maintenance_records
                ]
            }
            await broadcaster.broadcast(payload)
        await asyncio.sleep(0.1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telemetry backend")
    parser.add_argument("--interface", default=os.getenv("CAN_INTERFACE", "vcan0"))
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("BACKEND_PORT", 8000)))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://uav:uav_password_123@127.0.0.1:5432/uav_telemetry"))
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    runtime_args = parse_args()
    app = create_app(runtime_args.interface, Path(runtime_args.mapping), runtime_args.database_url)
    uvicorn.run(app, host=runtime_args.host, port=runtime_args.port, reload=False)
else:
    app = create_app(os.getenv("CAN_INTERFACE", "vcan0"), DEFAULT_MAPPING, os.getenv("DATABASE_URL", "postgresql://uav:uav_password_123@127.0.0.1:5432/uav_telemetry"))
