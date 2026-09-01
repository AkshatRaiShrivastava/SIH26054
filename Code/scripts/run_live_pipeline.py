import argparse
import os
import sqlite3
import subprocess
import sys
import time

# Get project root (parent of scripts directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Add project root to path so src modules can be imported
sys.path.insert(0, PROJECT_ROOT)

from src.utils.config import DATABASE_PATH


def reset_flight_data(flight_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM flight_condition WHERE flight_id = ?", (flight_id,))
        cursor.execute("DELETE FROM evaluations WHERE flight_id = ?", (flight_id,))
        cursor.execute("DELETE FROM telemetry WHERE flight_id = ?", (flight_id,))
        cursor.execute("DELETE FROM flights WHERE flight_id = ?", (flight_id,))
        conn.commit()
        print(f"Cleared prior data for flight {flight_id}")
    finally:
        conn.close()


def launch_process(name, args):
    print(f"Starting {name}...")
    return subprocess.Popen(
        args,
        cwd=PROJECT_ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Launch telemetry generation, physics evaluation, and dashboard together."
    )
    parser.add_argument("--flight-id", default="FL-LIVE-001", help="Flight ID to monitor")
    parser.add_argument("--zone", default="ior_maritime", help="Climate zone")
    parser.add_argument(
        "--fault-chance",
        type=float,
        default=0.2,
        help="Probability of fault injection (0.0 to 1.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port for Streamlit dashboard",
    )
    args = parser.parse_args()

    print("\n=== Starting Digital Twin pipeline ===")
    print(f"Flight ID: {args.flight_id}")
    print(f"Zone: {args.zone}")
    print(f"Fault chance: {args.fault_chance}")
    print(f"Dashboard URL: http://localhost:{args.port}\n")

    reset_flight_data(args.flight_id)
    subprocess.run(
        [sys.executable, "-m", "src.database.database"],
        cwd=PROJECT_ROOT,
        check=True,
    )

    gen_proc = launch_process(
        "telemetry generator",
        [
            sys.executable,
            "-m",
            "src.utils.generate_telemetry",
            "--flight-id",
            args.flight_id,
            "--zone",
            args.zone,
            "--fault-chance",
            str(args.fault_chance),
        ],
    )

    time.sleep(2)

    eval_proc = launch_process(
        "physics evaluator",
        [
            sys.executable,
            "-m",
            "src.core.physics_layer",
            "--flight-id",
            args.flight_id,
            "--live",
        ],
    )

    time.sleep(2)

    dash_proc = launch_process(
        "dashboard",
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/app/dashboard.py",
            "--server.headless",
            "true",
            "--server.port",
            str(args.port),
        ],
    )

    print("\nAll three processes are running. Open the dashboard in your browser.")
    print("Press Ctrl+C to stop the combined pipeline.\n")

    try:
        dash_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping pipeline...")
        for proc in (gen_proc, eval_proc, dash_proc):
            if proc.poll() is None:
                proc.terminate()
        try:
            for proc in (gen_proc, eval_proc, dash_proc):
                if proc.poll() is None:
                    proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            for proc in (gen_proc, eval_proc, dash_proc):
                if proc.poll() is None:
                    proc.kill()


if __name__ == "__main__":
    main()
