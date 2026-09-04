#!/usr/bin/env python3
"""Run the complete local telemetry stack in one terminal."""

from __future__ import annotations

import os
import shutil
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CAN_INTERFACE = os.environ.get("CAN_INTERFACE", "vcan0")
SIMULATOR_ARGS = shlex.split(os.environ.get("SIMULATOR_ARGS", ""))


def ensure_requirements() -> None:
    if shutil.which("npm") is None:
        raise SystemExit("npm is required. Install Node.js, then run `make install`.")
    if not (ROOT / "DashboardCode/frontend/node_modules").is_dir():
        raise SystemExit("Frontend dependencies are missing. Run `make install` first.")
    try:
        import can  # noqa: F401
    except ImportError as error:
        raise SystemExit("Python CAN dependencies are missing. Run `make install` first.") from error
    if CAN_INTERFACE not in {name for _, name in socket.if_nameindex()}:
        raise SystemExit(f"CAN interface '{CAN_INTERFACE}' does not exist. Run `make can-up` or set CAN_INTERFACE=can0 for hardware.")


def main() -> int:
    ensure_requirements()
    environment = os.environ.copy()
    environment["CAN_INTERFACE"] = CAN_INTERFACE
    services = [
        ("simulator", [sys.executable, "main.py", "--interface", CAN_INTERFACE, *SIMULATOR_ARGS], ROOT / "uav-engine-digital-twin"),
        ("backend", [sys.executable, "-m", "backend.app", "--interface", CAN_INTERFACE], ROOT / "DashboardCode"),
        ("frontend", ["npm", "run", "dev", "--", "--host", "0.0.0.0"], ROOT / "DashboardCode/frontend"),
    ]
    processes: list[subprocess.Popen[str]] = []
    try:
        for label, command, cwd in services:
            print(f"[dev] starting {label}: {' '.join(command)}", flush=True)
            processes.append(subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True))
        print("[dev] Dashboard: http://localhost:5173  |  API: http://localhost:8000/docs", flush=True)
        print("[dev] Press Ctrl+C to stop all services.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
