"""
Flask backend for the simple UAV simulation UI.
It runs the full mission once on start, then streams the recorded
telemetry to the browser via periodic polling.
"""
"""Live Flask API and web server for the UAV mission simulator."""

import bisect
import json
import os
import sys
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES_DIR = os.path.join(ROOT, "files")
sys.path.insert(0, FILES_DIR)

from mission_simulator import FLUCTUATION, MissionConfig, MissionSimulator
from mission_stages import load_dataset

FRONTEND_DIR = os.path.dirname(__file__)
MISSIONS_DIR = os.environ.get(
    "UAV_MISSIONS_DIR",
    "/tmp/uav-missions" if os.environ.get("VERCEL") else os.path.join(ROOT, "missions"),
)
DATASETS_DIR = os.path.join(ROOT, "datasets")
os.makedirs(MISSIONS_DIR, exist_ok=True)

app = Flask(__name__)
lock = threading.RLock()
session = {
    "sim": None,
    "dataset": None,
    "dataset_id": None,
    "playing": False,
    "speed": 1.0,
    "last_wall_time": None,
    "wall_accumulator": 0.0,
    "mission_name": "",
    "saved_path": None,
}


def _stage_config():
    dataset = session["dataset"]
    if dataset is None:
        return []
    return [
        {
            "name": name,
            "default_duration_s": default_duration,
            "duration_s": session["sim"].config.duration_for(name, default_duration)
            if session["sim"] else default_duration,
        }
        for name, _rpm, _throttle, _afr, _alt_frac, default_duration in dataset["stages"]
    ]


def _advance_locked():
    sim = session["sim"]
    if sim is None or not session["playing"]:
        return
    now = time.monotonic()
    previous = session["last_wall_time"] or now
    session["last_wall_time"] = now
    session["wall_accumulator"] += (now - previous) * session["speed"]
    while session["wall_accumulator"] >= sim.dt and not sim.realtime_finished:
        sim.step_realtime()
        session["wall_accumulator"] -= sim.dt
    if sim.realtime_finished:
        session["playing"] = False
        _save_locked()


def _save_locked():
    sim = session["sim"]
    if sim is None or not sim.timeseries:
        return None
    filename = f"{int(time.time())}_{session['mission_name'] or 'mission'}.json"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in filename)
    path = os.path.join(MISSIONS_DIR, safe_name)
    sim.save_mission(path, session["mission_name"] or "UAV mission")
    session["saved_path"] = path
    return path


def _state_payload():
    with lock:
        _advance_locked()
        sim = session["sim"]
        if sim is None:
            return {"status": "idle", "state": None, "events": [], "history": [], "stages": []}
        current = sim.timeseries[-1] if sim.timeseries else None
        return {
            "status": "playing" if session["playing"] else ("complete" if sim.realtime_finished else "paused"),
            "state": current,
            "history": sim.timeseries[-180:],
            "events": sim.events,
            "stages": _stage_config(),
            "duration_s": sim.time_s,
            "mission_name": session["mission_name"],
            "dataset_id": session["dataset_id"],
            "saved_path": session["saved_path"],
            "active_faults": list(sim.active_faults),
            "wear_enabled": sim.wear_enabled,
        }


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/config")
def config():
    dataset = _dataset_catalog().get(request.args.get("dataset_id", "rotax914_baseline_dataset"))
    if dataset is None:
        return jsonify({"error": "Unknown dataset"}), 404
    return jsonify({
        "dataset_id": dataset["dataset_id"],
        "dataset_label": dataset["label"],
        "environments": {
            key: {"isa_dev_c": values[0], "cruise_altitude_m": values[1],
                  "airfield_elevation_m": values[2], "label": values[3]}
            for key, values in dataset["environments"].items()
        },
        "stages": [
            {"name": name, "rpm": rpm, "throttle": throttle, "afr": afr,
             "altitude_frac": alt_frac, "default_duration_s": duration}
            for name, rpm, throttle, afr, alt_frac, duration in dataset["stages"]
        ],
        "channels": list(dataset["fluctuation"]),
    })


def _dataset_catalog():
    catalog = {}
    for filename in sorted(os.listdir(DATASETS_DIR)):
        if not filename.endswith(".json"):
            continue
        try:
            dataset = load_dataset(os.path.join(DATASETS_DIR, filename))
            catalog[dataset["dataset_id"]] = dataset
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return catalog


@app.get("/api/datasets")
def datasets():
    return jsonify([
        {"dataset_id": dataset["dataset_id"], "label": dataset["label"]}
        for dataset in _dataset_catalog().values()
    ])


@app.post("/api/start")
def start():
    data = request.get_json(silent=True) or {}
    dataset_id = str(data.get("dataset_id") or "rotax914_baseline_dataset")
    dataset = _dataset_catalog().get(dataset_id)
    if dataset is None:
        return jsonify({"error": f"Unknown dataset '{dataset_id}'"}), 400
    environment = data.get("environment", next(iter(dataset["environments"])))
    if environment not in dataset["environments"]:
        return jsonify({"error": "Unknown environment for selected dataset"}), 400
    try:
        durations = {str(k): float(v) for k, v in (data.get("stage_durations_s") or {}).items()}
        if any(value <= 0 for value in durations.values()):
            raise ValueError("stage durations must be positive")
        wear_rate = float(data.get("wear_pct_per_hour", 0))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    with lock:
        if session["sim"] is not None and session["sim"].timeseries:
            _save_locked()
        sim = MissionSimulator(MissionConfig(environment, durations, dataset=dataset), dt_s=1.0, seed=data.get("seed"))
        sim.start_realtime()
        if wear_rate > 0:
            sim.enable_wear(wear_rate)
        sim.step_realtime()
        session.update({
            "sim": sim, "dataset": dataset, "dataset_id": dataset_id,
            "playing": True, "speed": 1.0,
            "last_wall_time": time.monotonic(), "wall_accumulator": 0.0,
            "mission_name": str(data.get("mission_name") or "Interactive UAV mission"),
            "saved_path": None,
        })
    return jsonify(_state_payload())


@app.get("/api/state")
def state():
    return jsonify(_state_payload())


@app.post("/api/control")
def control():
    action = (request.get_json(silent=True) or {}).get("action")
    with lock:
        _advance_locked()
        sim = session["sim"]
        if sim is None:
            return jsonify({"error": "No mission is running"}), 400
        if action == "pause":
            session["playing"] = False
        elif action == "resume":
            session["playing"] = not sim.realtime_finished
            session["last_wall_time"] = time.monotonic()
        elif action == "reset":
            _save_locked()
            session.update({"sim": None, "dataset": None, "dataset_id": None,
                            "playing": False, "saved_path": None})
        elif action == "speed":
            try:
                session["speed"] = max(0.1, min(100.0, float((request.get_json(silent=True) or {}).get("value", 1))))
            except (TypeError, ValueError):
                return jsonify({"error": "speed must be numeric"}), 400
        else:
            return jsonify({"error": "unknown action"}), 400
    return jsonify(_state_payload())


@app.post("/api/fault")
def fault():
    data = request.get_json(silent=True) or {}
    channel = data.get("channel")
    with lock:
        sim = session["sim"]
        if sim is None:
            return jsonify({"error": "Start a mission first"}), 400
        try:
            if data.get("action") == "clear":
                sim.clear_fault(channel, float(data.get("ramp_s", 5)))
            else:
                sim.set_fault(channel, float(data.get("percent", 0)), float(data.get("ramp_s", 5)))
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(_state_payload())


@app.post("/api/wear")
def wear():
    data = request.get_json(silent=True) or {}
    with lock:
        sim = session["sim"]
        if sim is None:
            return jsonify({"error": "Start a mission first"}), 400
        try:
            if data.get("enabled", True):
                sim.enable_wear(float(data.get("pct_per_hour", 1)))
            else:
                sim.disable_wear()
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(_state_payload())


@app.post("/api/save")
def save():
    with lock:
        path = _save_locked()
    if path is None:
        return jsonify({"error": "No telemetry to save"}), 400
    return jsonify({"saved_path": path})


@app.get("/api/missions")
def missions():
    return jsonify(sorted(name for name in os.listdir(MISSIONS_DIR) if name.endswith(".json")))


if __name__ == "__main__":
    # Disable the auto‑reloader to keep in‑memory session state alive during development.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
