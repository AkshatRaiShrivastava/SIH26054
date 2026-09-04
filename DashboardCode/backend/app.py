"""FastAPI application for the telemetry backend."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

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
DEFAULT_DATABASE_URL = "postgresql://uav:uav@localhost:5432/uav_telemetry"


def create_app(interface: str, mapping_path: Path, database_url: str | None = None) -> FastAPI:
    broadcaster = TelemetryBroadcaster()
    recorder = FlightRecorder(
        database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        interface=interface,
        label=os.getenv("FLIGHT_LABEL", "unknown"),
    )
    service = TelemetryService(interface=interface, mapping_path=mapping_path, recorder=recorder)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service.start()
        broadcast_task = asyncio.create_task(_broadcast_loop(service, broadcaster))
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
        allow_credentials=True,
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

    @app.get("/api/flights")
    async def flights():
        connection = psycopg.connect(recorder.database_url)
        try:
            rows = connection.execute("SELECT * FROM flights ORDER BY started_at DESC").fetchall()
            columns = [column[0] for column in connection.execute("SELECT * FROM flights LIMIT 0").description]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            connection.close()

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(websocket: WebSocket):
        await websocket_telemetry_endpoint(websocket, broadcaster)

    return app


async def _broadcast_loop(service: TelemetryService, broadcaster: TelemetryBroadcaster) -> None:
    while True:
        snapshot = service.state.snapshot()
        if snapshot is not None:
            await broadcaster.broadcast(snapshot)
        await asyncio.sleep(0.1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telemetry backend")
    parser.add_argument("--interface", default=os.getenv("CAN_INTERFACE", "vcan0"))
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    return parser.parse_args()


if __name__ == "__main__":
    import uvicorn

    runtime_args = parse_args()
    app = create_app(runtime_args.interface, Path(runtime_args.mapping), runtime_args.database_url)
    uvicorn.run(app, host=runtime_args.host, port=runtime_args.port, reload=False)
else:
    app = create_app(os.getenv("CAN_INTERFACE", "vcan0"), DEFAULT_MAPPING)
