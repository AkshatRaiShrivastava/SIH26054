from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.db import SessionLocal, init_db
from backend.schemas import LiveSocketPayload, MissionStartRequest
from ingestion.listener import CANListener
from ingestion.processor import TelemetryProcessor
from physics.atmosphere import ambient_temperature_c
from rul.predict import predict_rul
from simulator.mission_profile import phase_name, phase_bounds

app = FastAPI(title="UAV Engine Digital Twin")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SIMULATION_STATE = {
    "running": False,
    "mission_id": None,
    "scenario": "normal",
    "speed_multiplier": 1.0,
    "processor": None,
    "listener": None,
    "last_result": None,
    "history": [],
    "websockets": defaultdict(list),
    "thread": None,
}
RUNTIME_DIR = os.getenv("RUNTIME_DIR", "/workspace/runtime")
SCENARIO_FILE = Path(RUNTIME_DIR) / "scenario.json"
STATUS_FILE = Path(RUNTIME_DIR) / "simulation_status.json"


def write_scenario_control(scenario: str, phase_durations_s: dict[int, float], mission_id: str) -> None:
    SCENARIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCENARIO_FILE.write_text(json.dumps({"scenario": scenario, "phase_durations_s": phase_durations_s, "mission_id": mission_id}), encoding="utf-8")


def read_simulation_status() -> dict | None:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_mission_timing(mission_id: str) -> tuple[float, int, float]:
    status = read_simulation_status()
    if status and status.get("mission_id") == mission_id:
        elapsed_s = float(status.get("elapsed_s", 0.0))
        phase_id = int(status.get("phase_id", 0))
        phase_durations = status.get("phase_durations_s")
        if phase_durations:
            total_duration = sum(float(v) for v in phase_durations.values())
        else:
            total_duration = 3600.0
        return elapsed_s, phase_id, total_duration
    return 0.0, 0, 3600.0


def timing_payload(mission_id: str) -> dict:
    elapsed_s, phase_id, total_duration_s = get_mission_timing(mission_id)
    return {
        "elapsed_s": elapsed_s,
        "phase_id": phase_id,
        "mission_total_s": total_duration_s,
        "remaining_s": max(0.0, total_duration_s - elapsed_s),
    }


def complete_simulation(mission_id: str) -> None:
    if SIMULATION_STATE["mission_id"] != mission_id or not SIMULATION_STATE["running"]:
        return
    if SIMULATION_STATE["listener"]:
        SIMULATION_STATE["listener"].stop()
    SIMULATION_STATE["running"] = False
    with SessionLocal() as db:
        db.execute(text("UPDATE mission_runs SET status = 'completed', ended_at = NOW() WHERE mission_id = :mission_id"), {"mission_id": mission_id})
        db.commit()


def monitor_simulation(mission_id: str) -> None:
    while SIMULATION_STATE["mission_id"] == mission_id and SIMULATION_STATE["running"]:
        try:
            status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            if status.get("mission_id") == mission_id and status.get("status") == "completed":
                complete_simulation(mission_id)
                return
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(0.25)


@app.on_event("startup")
def startup_event():
    init_db()
    ensure_model_training()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/simulation/start")
def start_simulation(payload: MissionStartRequest):
    if SIMULATION_STATE["listener"]:
        SIMULATION_STATE["listener"].stop()
    mission_id = f"MISSION-{uuid4().hex[:8]}"
    write_scenario_control(payload.scenario, payload.phase_durations_s, mission_id)
    SIMULATION_STATE["running"] = True
    SIMULATION_STATE["mission_id"] = mission_id
    SIMULATION_STATE["scenario"] = payload.scenario
    SIMULATION_STATE["speed_multiplier"] = payload.speed_multiplier
    SIMULATION_STATE["last_result"] = None
    SIMULATION_STATE["processor"] = TelemetryProcessor(mission_id)
    SIMULATION_STATE["listener"] = CANListener(mission_id, interface=os.getenv("CAN_INTERFACE", "vcan0"), callback=process_raw_record)
    SIMULATION_STATE["listener"].start()
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO mission_runs (mission_id, scenario, status, speed_multiplier) VALUES (:mission_id, :scenario, 'running', :speed_multiplier)"
            ),
            {"mission_id": mission_id, "scenario": payload.scenario, "speed_multiplier": payload.speed_multiplier},
        )
        db.commit()
    threading.Thread(target=monitor_simulation, args=(mission_id,), daemon=True).start()
    return {"mission_id": mission_id, "status": "running"}


@app.post("/api/simulation/stop")
def stop_simulation():
    if SIMULATION_STATE["listener"]:
        SIMULATION_STATE["listener"].stop()
    SIMULATION_STATE["running"] = False
    mission_id = SIMULATION_STATE["mission_id"]
    if mission_id:
        with SessionLocal() as db:
            db.execute(text("UPDATE mission_runs SET status = 'completed', ended_at = NOW() WHERE mission_id = :mission_id"), {"mission_id": mission_id})
            db.commit()
    return {"status": "stopped", "mission_id": mission_id}


@app.get("/api/simulation/status")
def get_status():
    timing = timing_payload(SIMULATION_STATE["mission_id"]) if SIMULATION_STATE["mission_id"] else {
        "elapsed_s": 0.0,
        "phase_id": 0,
        "mission_total_s": 0.0,
        "remaining_s": 0.0,
    }
    return {
        "running": SIMULATION_STATE["running"],
        "status": "running" if SIMULATION_STATE["running"] else "completed",
        "mission_id": SIMULATION_STATE["mission_id"],
        "scenario": SIMULATION_STATE["scenario"],
        "speed_multiplier": SIMULATION_STATE["speed_multiplier"],
        "listener_received_count": SIMULATION_STATE["listener"].received_count if SIMULATION_STATE["listener"] else 0,
        "listener_snapshot_count": SIMULATION_STATE["listener"].snapshot_count if SIMULATION_STATE["listener"] else 0,
        "listener_missing_signals": SIMULATION_STATE["listener"].missing_signals() if SIMULATION_STATE["listener"] else [],
        "last_update": SIMULATION_STATE["last_result"],
        **timing,
    }


@app.get("/api/missions")
def list_missions():
    with SessionLocal() as db:
        rows = db.execute(text("SELECT mission_id, scenario, started_at, COALESCE(ended_at, NOW()) as ended_at, status FROM mission_runs ORDER BY started_at DESC LIMIT 20")).fetchall()
    return [{
        "mission_id": row[0],
        "scenario": row[1],
        "started_at": str(row[2]),
        "ended_at": str(row[3]),
        "status": row[4],
    } for row in rows]


@app.get("/api/missions/{mission_id}")
def mission_detail(mission_id: str):
    with SessionLocal() as db:
        row = db.execute(text("SELECT mission_id, scenario, status, started_at, ended_at FROM mission_runs WHERE mission_id = :mission_id"), {"mission_id": mission_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {"mission_id": row[0], "scenario": row[1], "status": row[2], "started_at": str(row[3]), "ended_at": str(row[4])}


@app.get("/api/missions/{mission_id}/details")
def mission_details(mission_id: str):
    with SessionLocal() as db:
        mission = db.execute(text("SELECT mission_id, scenario, status, started_at, ended_at FROM mission_runs WHERE mission_id = :mission_id"), {"mission_id": mission_id}).fetchone()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
        latest = db.execute(text("SELECT rpm, cht_c, egt_c, oil_pressure_kpa, oil_temperature_c, fuel_flow_lph, vibration_mms, afr, battery_voltage, altitude_m, ambient_temp_c FROM raw_telemetry WHERE mission_id = :mission_id ORDER BY id DESC LIMIT 1"), {"mission_id": mission_id}).fetchone()
        metrics = db.execute(text("SELECT AVG(health_index), MAX(anomaly_score), COUNT(*) FROM computed_metrics WHERE mission_id = :mission_id"), {"mission_id": mission_id}).fetchone()
        faults = db.execute(text("SELECT fault_category, confidence, elapsed_s, driving_features FROM fault_events WHERE mission_id = :mission_id ORDER BY id DESC LIMIT 20"), {"mission_id": mission_id}).fetchall()
    return {
        "mission_id": mission[0], "scenario": mission[1], "status": mission[2],
        "started_at": str(mission[3]), "ended_at": str(mission[4]),
        "latest": dict(zip(["rpm", "cht_c", "egt_c", "oil_pressure_kpa", "oil_temperature_c", "fuel_flow_lph", "vibration_mms", "afr", "battery_voltage", "altitude_m", "ambient_temp_c"], latest)) if latest else None,
        "summary": {"average_health": metrics[0] or 0, "peak_anomaly": metrics[1] or 0, "samples": metrics[2] or 0},
        "faults": [{"category": fault[0], "confidence": fault[1], "elapsed_s": fault[2], "features": fault[3] or []} for fault in faults],
    }


@app.delete("/api/missions/{mission_id}")
def delete_mission(mission_id: str):
    with SessionLocal() as db:
        exists = db.execute(text("SELECT 1 FROM mission_runs WHERE mission_id = :mission_id"), {"mission_id": mission_id}).scalar()
        if not exists:
            raise HTTPException(status_code=404, detail="Mission not found")
        for table in ("raw_telemetry", "computed_metrics", "fault_events", "rul_predictions", "mission_runs"):
            db.execute(text(f"DELETE FROM {table} WHERE mission_id = :mission_id"), {"mission_id": mission_id})
        db.commit()
    return {"status": "deleted", "mission_id": mission_id}


@app.delete("/api/missions")
def clear_missions():
    with SessionLocal() as db:
        for table in ("raw_telemetry", "computed_metrics", "fault_events", "rul_predictions", "mission_runs"):
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    return {"status": "cleared"}


@app.get("/api/missions/{mission_id}/trend")
def mission_trend(mission_id: str, metric: str = "health_index"):
    with SessionLocal() as db:
        rows = db.execute(text(f"SELECT elapsed_s, {metric} FROM computed_metrics WHERE mission_id = :mission_id ORDER BY elapsed_s ASC LIMIT 200"), {"mission_id": mission_id}).fetchall()
    return {"metric": metric, "points": [{"elapsed_s": r[0], "value": r[1]} for r in rows]}


@app.get("/api/missions/{mission_id}/report")
def mission_report(mission_id: str):
    return {"mission_id": mission_id, "status": "prototype"}


@app.get("/api/missions/{mission_id}/maintenance")
def mission_maintenance(mission_id: str):
    return {"mission_id": mission_id, "recommendation": "NO MAINTENANCE ACTION INDICATED"}


@app.get("/api/missions/{mission_id}/replay")
def mission_replay(mission_id: str):
    with SessionLocal() as db:
        rows = db.execute(text("SELECT elapsed_s, rpm, cht_c, egt_c, oil_pressure_kpa, oil_temperature_c, fuel_flow_lph, vibration_mms, afr, battery_voltage, altitude_m, ambient_temp_c FROM raw_telemetry WHERE mission_id = :mission_id ORDER BY elapsed_s ASC"), {"mission_id": mission_id}).fetchall()
    return {"mission_id": mission_id, "points": [{
        "elapsed_s": r[0],
        "rpm": r[1],
        "cht_c": r[2],
        "egt_c": r[3],
        "oil_pressure_kpa": r[4],
        "oil_temperature_c": r[5],
        "fuel_flow_lph": r[6],
        "vibration_mms": r[7],
        "afr": r[8],
        "battery_voltage": r[9],
        "altitude_m": r[10],
        "ambient_temp_c": r[11],
    } for r in rows]}


@app.websocket("/ws/live/{mission_id}")
async def ws_live(websocket: WebSocket, mission_id: str):
    await websocket.accept()
    SIMULATION_STATE["websockets"][mission_id].append(websocket)
    try:
        while True:
            if SIMULATION_STATE["last_result"] and SIMULATION_STATE["last_result"].get("mission_id") == mission_id:
                await websocket.send_json(SIMULATION_STATE["last_result"])
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


def process_raw_record(record: dict):
    mission_id = record["mission_id"]
    processor = SIMULATION_STATE["processor"]
    if processor is None:
        return
    sim_elapsed, sim_phase, sim_total = get_mission_timing(mission_id)
    record["elapsed_s"] = sim_elapsed
    record["phase_id"] = sim_phase
    metrics = processor.process(record)
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO raw_telemetry (mission_id, elapsed_s, phase_id, rpm, cht_c, egt_c, oil_pressure_kpa, oil_temperature_c, fuel_flow_lph, vibration_mms, afr, battery_voltage, altitude_m, ambient_temp_c) VALUES (:mission_id, :elapsed_s, :phase_id, :rpm, :cht_c, :egt_c, :oil_pressure_kpa, :oil_temperature_c, :fuel_flow_lph, :vibration_mms, :afr, :battery_voltage, :altitude_m, :ambient_temp_c)"
            ),
            {"mission_id": mission_id, "elapsed_s": sim_elapsed, "phase_id": sim_phase, "rpm": record.get("rpm", 0.0), "cht_c": record.get("cht_c", 0.0), "egt_c": record.get("egt_c", 0.0), "oil_pressure_kpa": record.get("oil_pressure_kpa", 0.0), "oil_temperature_c": record.get("oil_temperature_c", 0.0), "fuel_flow_lph": record.get("fuel_flow_lph", 0.0), "vibration_mms": record.get("vibration_mms", 0.0), "afr": record.get("afr", 14.7), "battery_voltage": record.get("battery_voltage", 13.5), "altitude_m": record.get("altitude_m", 0.0), "ambient_temp_c": record.get("ambient_temp_c", 15.0)},
        )
        db.execute(
            text(
                "INSERT INTO computed_metrics (mission_id, elapsed_s, phase_id, cht_expected, cht_deviation_pct, egt_expected, egt_deviation_pct, oil_pressure_expected, oil_pressure_deviation_pct, oil_temp_expected, oil_temp_deviation_pct, fuel_flow_expected, fuel_flow_deviation_pct, vibration_baseline, vibration_deviation_pct, anomaly_score, is_anomaly, model_version, health_index) VALUES (:mission_id, :elapsed_s, :phase_id, :cht_expected, :cht_deviation_pct, :egt_expected, :egt_deviation_pct, :oil_pressure_expected, :oil_pressure_deviation_pct, :oil_temp_expected, :oil_temp_deviation_pct, :fuel_flow_expected, :fuel_flow_deviation_pct, :vibration_baseline, :vibration_deviation_pct, :anomaly_score, :is_anomaly, :model_version, :health_index)"
            ),
            {
                "mission_id": mission_id,
                "elapsed_s": sim_elapsed,
                "phase_id": sim_phase,
                "cht_expected": metrics["computed"]["cht_expected"],
                "cht_deviation_pct": metrics["computed"]["cht_deviation_pct"],
                "egt_expected": metrics["computed"]["egt_expected"],
                "egt_deviation_pct": metrics["computed"]["egt_deviation_pct"],
                "oil_pressure_expected": metrics["computed"]["oil_pressure_expected"],
                "oil_pressure_deviation_pct": metrics["computed"]["oil_pressure_deviation_pct"],
                "oil_temp_expected": metrics["computed"]["oil_temp_expected"],
                "oil_temp_deviation_pct": metrics["computed"]["oil_temp_deviation_pct"],
                "fuel_flow_expected": metrics["computed"]["fuel_flow_expected"],
                "fuel_flow_deviation_pct": metrics["computed"]["fuel_flow_deviation_pct"],
                "vibration_baseline": metrics["computed"]["vibration_baseline"],
                "vibration_deviation_pct": metrics["computed"]["vibration_deviation_pct"],
                "anomaly_score": metrics["computed"]["anomaly_score"],
                "is_anomaly": metrics["computed"]["is_anomaly"],
                "model_version": metrics["computed"]["model_version"],
                "health_index": metrics["computed"]["health_index"],
            },
        )
        if metrics["fault_alert"]:
            db.execute(text("INSERT INTO fault_events (mission_id, elapsed_s, fault_category, confidence, driving_features) VALUES (:mission_id, :elapsed_s, :fault_category, :confidence, :driving_features)"), {"mission_id": mission_id, "elapsed_s": sim_elapsed, "fault_category": metrics["fault_alert"]["fault_category"], "confidence": metrics["fault_alert"]["confidence"], "driving_features": metrics["fault_alert"]["driving_features"]})
        db.commit()
    if metrics["fault_alert"]:
        print(json.dumps(metrics["fault_alert"]))
    result = {
        "channel": "live",
        "mission_id": mission_id,
        "elapsed_s": sim_elapsed,
        "phase_id": sim_phase,
        "phase_name": phase_name(sim_phase),
        "mission_total_s": sim_total,
        "remaining_s": max(0.0, sim_total - sim_elapsed),
        "raw": {
            "rpm": float(record.get("rpm", 0.0)),
            "cht_c": float(record.get("cht_c", 0.0)),
            "egt_c": float(record.get("egt_c", 0.0)),
            "oil_pressure_kpa": float(record.get("oil_pressure_kpa", 0.0)),
            "oil_temperature_c": float(record.get("oil_temperature_c", 0.0)),
            "fuel_flow_lph": float(record.get("fuel_flow_lph", 0.0)),
            "vibration_mms": float(record.get("vibration_mms", 0.0)),
            "afr": float(record.get("afr", 14.7)),
            "battery_voltage": float(record.get("battery_voltage", 13.5)),
            "altitude_m": float(record.get("altitude_m", 0.0)),
            "ambient_temp_c": float(record.get("ambient_temp_c", 15.0)),
        },
        "computed": {
            "health_index": float(metrics["computed"]["health_index"]),
            "anomaly_score": float(metrics["computed"]["anomaly_score"]),
            "is_anomaly": bool(metrics["computed"]["is_anomaly"]),
            "deviations_pct": {
                "cht": float(metrics["computed"]["cht_deviation_pct"]),
                "egt": float(metrics["computed"]["egt_deviation_pct"]),
                "oil_pressure": float(metrics["computed"]["oil_pressure_deviation_pct"]),
                "oil_temp": float(metrics["computed"]["oil_temp_deviation_pct"]),
                "fuel_flow": float(metrics["computed"]["fuel_flow_deviation_pct"]),
                "vibration": float(metrics["computed"]["vibration_deviation_pct"]),
            },
        },
        "physics": metrics["physics"],
        "fault_alert": metrics["fault_alert"],
        "rul": {
            "predicted_rul_minutes": 0,
            "confidence_band_minutes": 0,
            "driving_channel": "n/a",
        },
        "mission_total_s": sim_total,
        "remaining_s": max(0.0, sim_total - sim_elapsed),
    }
    SIMULATION_STATE["last_result"] = result
    if mission_id in SIMULATION_STATE["websockets"]:
        for ws in SIMULATION_STATE["websockets"][mission_id]:
            try:
                ws.send_json(result)
            except Exception:
                pass


def ensure_model_training():
    from ml.train import train_model
    from rul.train import train_rul_model
    try:
        train_model()
        train_rul_model()
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("BACKEND_PORT", "8000")))
