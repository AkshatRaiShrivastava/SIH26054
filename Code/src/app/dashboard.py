"""
dashboard.py — STEPS 5-7: Digital Twin Dashboard with live and historical views.

Streamlit-based dashboard showing:
- Live UAV telemetry with parameter gauges and health status
- Historical flight data with time scrubber
- Environmental advisories (icing risk, corrosion)
- Subsystem health breakdown

Usage:
    streamlit run dashboard.py
"""

import os
import random
import subprocess
import sys
import time

# Add project root to path for imports when running with streamlit
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from collections import defaultdict
import numpy as np

from src.utils import config
from src.database.database import get_connection, close_connection


# ============================================================================
# PAGE CONFIG AND LAYOUT
# ============================================================================

st.set_page_config(
    page_title="Digital Twin Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .metric-box { background: #f0f2f6; padding: 10px; border-radius: 5px; margin: 5px; }
        .status-normal { color: #28a745; font-weight: bold; }
        .status-caution { color: #ffc107; font-weight: bold; }
        .status-critical { color: #dc3545; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# DATABASE UTILITIES
# ============================================================================

def get_db():
    """Open a fresh SQLite connection that is safe across Streamlit threads."""
    db_path = config.DATABASE_PATH
    return sqlite3.connect(db_path, check_same_thread=False)


def query_flights():
    """Get all live or completed flights so the dashboard can show work in progress."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT flight_id, start_time, climate_zone, fault_injected "
            "FROM flights WHERE status IN ('in_progress', 'complete') ORDER BY start_time DESC"
        )
        rows = cursor.fetchall()
        return [
            {
                "flight_id": r[0],
                "start_time": r[1],
                "climate_zone": r[2],
                "fault_injected": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_latest_telemetry(flight_id: str):
    """Get the most recent telemetry packet for a flight."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM telemetry WHERE flight_id = ? ORDER BY mission_time_s DESC LIMIT 1",
            (flight_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))
    finally:
        conn.close()


def get_latest_flight_condition(flight_id: str):
    """Get the most recent flight condition for a flight."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM flight_condition WHERE flight_id = ? ORDER BY mission_time_s DESC LIMIT 1",
            (flight_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))
    finally:
        conn.close()


def get_telemetry_at_time(flight_id: str, mission_time_s: float):
    """Get telemetry at or nearest to a specific mission time."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM telemetry
            WHERE flight_id = ? AND mission_time_s <= ?
            ORDER BY mission_time_s DESC LIMIT 1
            """,
            (flight_id, mission_time_s),
        )
        row = cursor.fetchone()
        if not row:
            return None
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))
    finally:
        conn.close()


def get_flight_condition_at_time(flight_id: str, mission_time_s: float):
    """Get flight condition at or nearest to a specific mission time."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM flight_condition
            WHERE flight_id = ? AND mission_time_s <= ?
            ORDER BY mission_time_s DESC LIMIT 1
            """,
            (flight_id, mission_time_s),
        )
        row = cursor.fetchone()
        if not row:
            return None
        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))
    finally:
        conn.close()


def get_flight_duration(flight_id: str):
    """Get total mission time for a flight."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(mission_time_s) FROM telemetry WHERE flight_id = ?",
            (flight_id,),
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else 0
    finally:
        conn.close()


def get_trend_data(flight_id: str, parameter: str, mission_time_start: float):
    """Get trend data for a parameter over last N minutes."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT mission_time_s, actual, expected, status
            FROM evaluations
            WHERE flight_id = ? AND parameter = ? AND mission_time_s >= ?
            ORDER BY mission_time_s ASC
            """,
            (flight_id, parameter, mission_time_start),
        )
        rows = cursor.fetchall()
        return [
            {
                "time": r[0],
                "actual": r[1],
                "expected": r[2],
                "status": r[3],
            }
            for r in rows
        ]
    finally:
        conn.close()


def fetch_latest_evals_for_params(flight_id: str, params: list[str]):
    """Return the latest evaluation row for each requested parameter."""
    if not params:
        return {}

    conn = get_db()
    try:
        cursor = conn.cursor()
        placeholders = ", ".join("?" for _ in params)
        query = f"""
            SELECT parameter, actual, expected, status
            FROM evaluations
            WHERE flight_id = ? AND parameter IN ({placeholders})
            AND mission_time_s = (
                SELECT MAX(mission_time_s)
                FROM evaluations e2
                WHERE e2.flight_id = evaluations.flight_id
                  AND e2.parameter = evaluations.parameter
            )
        """
        cursor.execute(query, [flight_id, *params])
        rows = cursor.fetchall()
        return {r[0]: {"actual": r[1], "expected": r[2], "status": r[3]} for r in rows}
    finally:
        conn.close()


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_status_banner(status: str, icing_risk: str = "LOW"):
    """Render top banner with overall status and icing advisory."""
    col1, col2 = st.columns([3, 1])

    with col1:
        # Overall status
        if status == "normal":
            st.markdown(
                f"<div class='status-normal'>🟢 NORMAL - All systems nominal</div>",
                unsafe_allow_html=True,
            )
        elif status == "caution":
            st.markdown(
                f"<div class='status-caution'>🟡 CAUTION - Investigate anomalies</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='status-critical'>🔴 CRITICAL - Immediate attention required</div>",
                unsafe_allow_html=True,
            )

    with col2:
        # Icing advisory
        if icing_risk == "HIGH":
            st.markdown(
                f"<div class='status-critical'>❄️ HIGH ICING RISK</div>",
                unsafe_allow_html=True,
            )
        elif icing_risk == "MODERATE":
            st.markdown(
                f"<div class='status-caution'>❄️ MODERATE ICING RISK</div>",
                unsafe_allow_html=True,
            )


def render_parameter_gauge(
    param_name: str, actual: float, expected: float, status: str, unit: str
):
    """Render a single parameter gauge."""
    # Color based on status
    if status == "normal":
        color = "#28a745"
    elif status == "caution":
        color = "#ffc107"
    else:
        color = "#dc3545"

    deviation = 100 * (actual - expected) / expected if expected != 0 else 0
    deviation_str = f"{deviation:+.1f}%" if abs(deviation) > 0.1 else "0.0%"

    st.metric(
        label=f"{param_name} [{status.upper()}]",
        value=f"{actual:.1f} {unit}",
        delta=f"{expected:.1f} expected ({deviation_str})",
        delta_color="inverse" if status != "normal" else "normal",
    )


def render_subsystem_health(subsys_health: dict):
    """Render subsystem health scores."""
    cols = st.columns(4)
    for i, (subsys, score) in enumerate(subsys_health.items()):
        with cols[i]:
            # Color gradient
            if score >= 90:
                color = "#28a745"
            elif score >= 50:
                color = "#ffc107"
            else:
                color = "#dc3545"

            st.markdown(
                f"""
                <div style="background: {color}; color: white; padding: 15px; 
                     border-radius: 5px; text-align: center;">
                    <h4>{subsys.replace('_', ' ').title()}</h4>
                    <h2>{score:.0f}%</h2>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_trend_chart(flight_id: str, parameter: str, mission_time_end: float):
    """Render trend chart for a parameter."""
    # Get last 30 minutes of data
    mission_time_start = max(0, mission_time_end - 1800)

    trend_data = get_trend_data(flight_id, parameter, mission_time_start)

    if not trend_data:
        st.info(f"No trend data available for {parameter}")
        return

    df = pd.DataFrame(trend_data)

    # Create trend chart
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["time"] / 60,  # Convert to minutes
            y=df["actual"],
            mode="lines",
            name="Actual",
            line=dict(color="blue"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["time"] / 60,
            y=df["expected"],
            mode="lines",
            name="Expected",
            line=dict(color="green", dash="dash"),
        )
    )

    # Color regions by status
    status_changes = df[df["status"] != df["status"].shift()].index
    colors = {"normal": "rgba(40, 167, 69, 0.1)", "caution": "rgba(255, 193, 7, 0.1)", "critical": "rgba(220, 53, 69, 0.1)"}

    fig.update_layout(
        title=f"{parameter} Trend (Last 30 min)",
        xaxis_title="Mission Time (min)",
        yaxis_title="Value",
        hovermode="x unified",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main dashboard app."""
    st.session_state.setdefault("live_feed_enabled", True)
    refresh_interval_s = st.sidebar.slider("Auto-refresh every", 2, 30, 5, 1)
    if st.session_state.get("live_feed_enabled", True):
        st_autorefresh(interval=refresh_interval_s * 1000, key="dashboard_autorefresh")

    st.title("✈️ Digital Twin Dashboard")
    st.markdown("---")

    # Sidebar: Mode selection
    mode = st.sidebar.radio("Select View", ["Live Flight", "Flight History", "Maintenance"])

    if mode == "Live Flight":
        render_live_view()
    elif mode == "Flight History":
        render_history_view()
    else:
        render_maintenance_view()


def generate_unique_flight_id(prefix: str = "FL-AUTO") -> str:
    """Create a unique flight ID so each new UAV does not overwrite the previous flight."""
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    suffix = random.randint(100, 999)
    return f"{prefix}-{timestamp}-{suffix}"


def create_new_uav_flight(climate_zone: str = "ior_maritime", fault_chance: float = 0.2):
    """Launch a fresh UAV flight pipeline so it appears as a new flight record."""
    flight_id = generate_unique_flight_id()
    ROOT = os.path.dirname(os.path.abspath(__file__))

    subprocess.Popen(
        [
            sys.executable,
            "generate_telemetry.py",
            "--flight-id",
            flight_id,
            "--zone",
            climate_zone,
            "--fault-chance",
            str(fault_chance),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    subprocess.Popen(
        [sys.executable, "physics_layer.py", "--flight-id", flight_id, "--live"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return flight_id


def ensure_demo_flight():
    """Create a demo flight automatically when no flights are present."""
    flight_id = generate_unique_flight_id()
    ROOT = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(
        [
            sys.executable,
            "generate_telemetry.py",
            "--flight-id",
            flight_id,
            "--zone",
            "ior_maritime",
            "--fault-chance",
            "0.2",
        ],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    subprocess.run(
        [sys.executable, "physics_layer.py", "--flight-id", flight_id, "--live"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return flight_id


def build_manual_snapshot_condition(snapshot: dict, flight_id: str):
    """Convert a user-entered manual telemetry snapshot into a dashboard condition record."""
    from src.core.environmental_physics import EnvironmentalPhysics
    from src.core.physics_layer import PhysicsEvaluator

    snapshot_row = {
        "flight_id": flight_id,
        "mission_time_s": float(snapshot.get("mission_time_s", 0.0)),
        "timestamp": snapshot.get("timestamp") or datetime.utcnow().isoformat(),
        "phase": snapshot.get("phase") or "cruise",
        "rpm": float(snapshot.get("rpm", 3200)),
        "cht_c": float(snapshot.get("cht_c", 150)),
        "egt_c": float(snapshot.get("egt_c", 700)),
        "oil_temp_c": float(snapshot.get("oil_temp_c", 90)),
        "oil_pressure_psi": float(snapshot.get("oil_pressure_psi", 45)),
        "fuel_flow_lph": float(snapshot.get("fuel_flow_lph", 32)),
        "vibration_g": float(snapshot.get("vibration_g", 0.5)),
        "battery_v": float(snapshot.get("battery_v", 14.0)),
        "afr": float(snapshot.get("afr", 13.2)),
        "altitude_m": float(snapshot.get("altitude_m", 3000)),
        "ambient_temp_c": float(snapshot.get("ambient_temp_c", 15)),
        "humidity_pct": float(snapshot.get("humidity_pct", 50)),
        "pressure_altitude_m": float(snapshot.get("pressure_altitude_m", 3000)),
        "precipitation": int(snapshot.get("precipitation", 0)),
        "hours_since_filter_service": float(snapshot.get("hours_since_filter_service", 0)),
        "maritime_hours_cumulative": float(snapshot.get("maritime_hours_cumulative", 0)),
        "climate_zone": snapshot.get("climate_zone") or "ior_maritime",
    }

    evaluator = PhysicsEvaluator(flight_id=flight_id, is_live=False)
    evaluations = evaluator.evaluate_packet(snapshot_row)
    parameter_statuses = {entry["parameter"]: entry["status"] for entry in evaluations}
    subsystem_health = evaluator.compute_subsystem_health(parameter_statuses)
    overall_status = evaluator.compute_overall_status(subsystem_health)
    icing_advisory = EnvironmentalPhysics().classify_icing_risk(
        snapshot_row.get("ambient_temp_c", 15),
        snapshot_row.get("humidity_pct", 50),
    )

    return {
        "overall_status": overall_status,
        "subsystem_health_json": json.dumps(subsystem_health),
        "icing_advisory": icing_advisory,
        "fault_category": None,
        "_evaluations": evaluations,
    }


def build_manual_snapshot_evaluations(snapshot: dict, flight_id: str):
    """Return the evaluation rows built from the user-entered manual snapshot."""
    from src.core.physics_layer import PhysicsEvaluator

    snapshot_row = {
        "flight_id": flight_id,
        "mission_time_s": float(snapshot.get("mission_time_s", 0.0)),
        "timestamp": snapshot.get("timestamp") or datetime.utcnow().isoformat(),
        "phase": snapshot.get("phase") or "cruise",
        "rpm": float(snapshot.get("rpm", 3200)),
        "cht_c": float(snapshot.get("cht_c", 150)),
        "egt_c": float(snapshot.get("egt_c", 700)),
        "oil_temp_c": float(snapshot.get("oil_temp_c", 90)),
        "oil_pressure_psi": float(snapshot.get("oil_pressure_psi", 45)),
        "fuel_flow_lph": float(snapshot.get("fuel_flow_lph", 32)),
        "vibration_g": float(snapshot.get("vibration_g", 0.5)),
        "battery_v": float(snapshot.get("battery_v", 14.0)),
        "afr": float(snapshot.get("afr", 13.2)),
        "altitude_m": float(snapshot.get("altitude_m", 3000)),
        "ambient_temp_c": float(snapshot.get("ambient_temp_c", 15)),
        "humidity_pct": float(snapshot.get("humidity_pct", 50)),
        "pressure_altitude_m": float(snapshot.get("pressure_altitude_m", 3000)),
        "precipitation": int(snapshot.get("precipitation", 0)),
        "hours_since_filter_service": float(snapshot.get("hours_since_filter_service", 0)),
        "maritime_hours_cumulative": float(snapshot.get("maritime_hours_cumulative", 0)),
        "climate_zone": snapshot.get("climate_zone") or "ior_maritime",
    }

    evaluator = PhysicsEvaluator(flight_id=flight_id, is_live=False)
    eval_rows = evaluator.evaluate_packet(snapshot_row)
    return {row["parameter"]: {"actual": row["actual"], "expected": row["expected"], "status": row["status"]} for row in eval_rows}


def render_manual_snapshot_form(selected_flight: str):
    """Display a form for manual snapshot entry and use the values in the current live view."""
    default_snapshot = get_latest_telemetry(selected_flight) or {}
    if not default_snapshot:
        default_snapshot = {
            "mission_time_s": 0.0,
            "phase": "cruise",
            "rpm": 3200,
            "cht_c": 150,
            "egt_c": 700,
            "oil_temp_c": 90,
            "oil_pressure_psi": 45,
            "fuel_flow_lph": 32,
            "vibration_g": 0.5,
            "battery_v": 14.0,
            "afr": 13.2,
            "altitude_m": 3000,
            "ambient_temp_c": 15,
            "humidity_pct": 50,
            "pressure_altitude_m": 3000,
            "precipitation": 0,
            "hours_since_filter_service": 0,
            "maritime_hours_cumulative": 0,
            "climate_zone": "ior_maritime",
        }

    with st.form("manual_snapshot_form"):
        st.subheader("Manual Data Snapshot")
        st.caption("Enter the values below and submit them to use this snapshot as the live result.")

        col1, col2 = st.columns(2)
        with col1:
            phase = st.selectbox("Phase", ["preflight", "takeoff", "climb", "cruise", "descent", "landing"], index=["preflight", "takeoff", "climb", "cruise", "descent", "landing"].index(default_snapshot.get("phase", "cruise")))
            mission_time_s = st.number_input("Mission Time (s)", value=float(default_snapshot.get("mission_time_s", 0.0)), step=1.0)
            rpm = st.number_input("RPM", value=float(default_snapshot.get("rpm", 3200)), step=10.0)
            cht_c = st.number_input("CHT (°C)", value=float(default_snapshot.get("cht_c", 150)), step=1.0)
            egt_c = st.number_input("EGT (°C)", value=float(default_snapshot.get("egt_c", 700)), step=5.0)
            oil_temp_c = st.number_input("Oil Temp (°C)", value=float(default_snapshot.get("oil_temp_c", 90)), step=1.0)
            oil_pressure_psi = st.number_input("Oil Pressure (psi)", value=float(default_snapshot.get("oil_pressure_psi", 45)), step=1.0)
            fuel_flow_lph = st.number_input("Fuel Flow (L/h)", value=float(default_snapshot.get("fuel_flow_lph", 32)), step=1.0)
            vibration_g = st.number_input("Vibration (g)", value=float(default_snapshot.get("vibration_g", 0.5)), step=0.1)

        with col2:
            battery_v = st.number_input("Battery (V)", value=float(default_snapshot.get("battery_v", 14.0)), step=0.1)
            afr = st.number_input("AFR", value=float(default_snapshot.get("afr", 13.2)), step=0.1)
            altitude_m = st.number_input("Altitude (m)", value=float(default_snapshot.get("altitude_m", 3000)), step=10.0)
            ambient_temp_c = st.number_input("Ambient Temp (°C)", value=float(default_snapshot.get("ambient_temp_c", 15)), step=1.0)
            humidity_pct = st.number_input("Humidity (%)", value=float(default_snapshot.get("humidity_pct", 50)), step=1.0)
            pressure_altitude_m = st.number_input("Pressure Altitude (m)", value=float(default_snapshot.get("pressure_altitude_m", 3000)), step=10.0)
            precipitation = st.number_input("Precipitation", value=int(default_snapshot.get("precipitation", 0)), step=1)
            hours_since_filter_service = st.number_input("Filter Hours", value=float(default_snapshot.get("hours_since_filter_service", 0)), step=1.0)
            maritime_hours_cumulative = st.number_input("Maritime Hours", value=float(default_snapshot.get("maritime_hours_cumulative", 0)), step=1.0)
            climate_zone = st.selectbox("Climate Zone", ["ior_maritime", "desert", "himalayan", "monsoon_belt"], index=["ior_maritime", "desert", "himalayan", "monsoon_belt"].index(default_snapshot.get("climate_zone", "ior_maritime")))

        submitted = st.form_submit_button("Submit Snapshot")
        if submitted:
            st.session_state.manual_snapshot = {
                "flight_id": selected_flight,
                "mission_time_s": mission_time_s,
                "timestamp": datetime.utcnow().isoformat(),
                "phase": phase,
                "rpm": rpm,
                "cht_c": cht_c,
                "egt_c": egt_c,
                "oil_temp_c": oil_temp_c,
                "oil_pressure_psi": oil_pressure_psi,
                "fuel_flow_lph": fuel_flow_lph,
                "vibration_g": vibration_g,
                "battery_v": battery_v,
                "afr": afr,
                "altitude_m": altitude_m,
                "ambient_temp_c": ambient_temp_c,
                "humidity_pct": humidity_pct,
                "pressure_altitude_m": pressure_altitude_m,
                "precipitation": precipitation,
                "hours_since_filter_service": hours_since_filter_service,
                "maritime_hours_cumulative": maritime_hours_cumulative,
                "climate_zone": climate_zone,
            }
            st.session_state.manual_snapshot_active = True
            st.session_state.feed_snapshot_open = False
            st.session_state.live_feed_enabled = False
            st.success("Snapshot applied successfully.")


def render_live_view():
    """Render live flight monitoring view."""
    st.session_state.setdefault("selected_live_flight", None)
    st.session_state.setdefault("manual_snapshot", None)
    st.session_state.setdefault("manual_snapshot_active", False)
    st.session_state.setdefault("feed_snapshot_open", False)
    st.session_state.setdefault("live_feed_enabled", True)

    st.header("Live Flight Monitoring")

    flights = query_flights()
    if not flights:
        st.info("No flights available. Starting a demo flight automatically...")
        st.session_state.selected_live_flight = ensure_demo_flight()
        st.rerun()
        return

    if st.button("➕ New UAV Flight"):
        st.session_state.selected_live_flight = create_new_uav_flight()
        st.session_state.live_feed_enabled = True
        st.session_state.manual_snapshot = None
        st.session_state.manual_snapshot_active = False
        st.session_state.feed_snapshot_open = False
        st.rerun()

    live_cols = st.columns([1, 1, 1])
    with live_cols[0]:
        if st.session_state.get("live_feed_enabled", True):
            if st.button("⏸ Pause Live Feed"):
                st.session_state.live_feed_enabled = False
                st.session_state.feed_snapshot_open = False
                st.rerun()
        else:
            if st.button("▶ Resume Live Feed"):
                st.session_state.live_feed_enabled = True
                st.session_state.manual_snapshot = None
                st.session_state.manual_snapshot_active = False
                st.session_state.feed_snapshot_open = False
                st.rerun()
    with live_cols[1]:
        if st.button("📡 Feed Data Snapshot"):
            st.session_state.live_feed_enabled = False
            st.session_state.feed_snapshot_open = True
            st.session_state.manual_snapshot_active = False
            st.rerun()

    # Try to find an in-progress flight
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT flight_id FROM flights WHERE status = 'in_progress' ORDER BY start_time DESC LIMIT 1"
    )
    in_progress = cursor.fetchone()

    if in_progress:
        selected_flight = st.session_state.selected_live_flight or in_progress[0]
        if selected_flight not in {f["flight_id"] for f in flights}:
            selected_flight = in_progress[0]
        st.info(f"🔴 Live: {selected_flight}")
    else:
        flight_options = [f"{f['flight_id']} ({f['climate_zone']})" for f in flights]
        if st.session_state.selected_live_flight and st.session_state.selected_live_flight in {f["flight_id"] for f in flights}:
            default_idx = next(i for i, option in enumerate(flight_options) if option.startswith(st.session_state.selected_live_flight))
        else:
            default_idx = 0
        selected = st.selectbox("Select Flight", flight_options, index=default_idx, key="live_flight_selector")
        selected_flight = selected.split(" ")[0]
        st.session_state.selected_live_flight = selected_flight

    if st.session_state.get("feed_snapshot_open", False):
        render_manual_snapshot_form(selected_flight)
        st.warning("📡 Snapshot mode is active. Submit the form to use the custom data for the live result.")
        return

    if st.session_state.get("manual_snapshot_active", False):
        st.warning("🧪 Manual snapshot override is active. Values are being generated from the submitted feed data.")
    elif not st.session_state.get("live_feed_enabled", True):
        st.warning("📡 Static data mode is active. Click Resume Live Feed to continue live updates.")

    # Get latest data
    if st.session_state.get("manual_snapshot_active", False) and st.session_state.get("manual_snapshot") and st.session_state.get("manual_snapshot", {}).get("flight_id") == selected_flight:
        telemetry = st.session_state.manual_snapshot
        condition = build_manual_snapshot_condition(telemetry, selected_flight)
        evals = build_manual_snapshot_evaluations(telemetry, selected_flight)
    else:
        telemetry = get_latest_telemetry(selected_flight)
        condition = get_latest_flight_condition(selected_flight)
        evals = None

    if not telemetry or not condition:
        st.error("No data available for this flight")
        return

    # Parse health JSON
    subsys_health = json.loads(condition.get("subsystem_health_json", "{}"))

    # Top banner
    render_status_banner(condition["overall_status"], condition.get("icing_advisory", "LOW"))

    # Mission info
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mission Time", f"{telemetry['mission_time_s']/60:.1f} min")
    col2.metric("Phase", telemetry["phase"])
    col3.metric("Altitude", f"{telemetry['altitude_m']:.0f} m")
    col4.metric("RPM", f"{telemetry['rpm']:.0f}")

    st.markdown("---")

    # Subsystem health
    st.subheader("Subsystem Health")
    render_subsystem_health(subsys_health)

    st.markdown("---")

    # Parameter gauges grouped by subsystem
    st.subheader("Engine Parameters")

    # ML panel: anomaly score and (placeholder) RUL
    try:
        cols_ml = st.columns([3, 1])
        with cols_ml[1]:
            st.subheader("ML Insights")
            # Try to import inference helpers from ml package
            try:
                from ml.infer import load_model as ml_load_model
                from ml.infer import get_latest_window as ml_get_latest_window
                from ml.infer import score_window as ml_score_window

                model_path = os.path.join(PROJECT_ROOT, "ml", "models", "anomaly_iforest.pkl")
                if os.path.exists(model_path):
                    ml_model = ml_load_model(model_path)
                    conn_ml = get_db()
                    try:
                        df_win = ml_get_latest_window(conn_ml, selected_flight, window_size=30)
                    finally:
                        conn_ml.close()

                    score = ml_score_window(df_win, ml_model)
                    if np.isnan(score):
                        st.info("No recent telemetry window for ML scoring")
                    else:
                        # Simple thresholds for display (calibrate later)
                        if score > 0.5:
                            tag = "CRITICAL"
                            color = "#dc3545"
                        elif score > 0.2:
                            tag = "CAUTION"
                            color = "#ffc107"
                        else:
                            tag = "NORMAL"
                            color = "#28a745"

                        st.markdown(f"**Anomaly score:** <span style='color:{color}'>{score:.3f} ({tag})</span>", unsafe_allow_html=True)
                        st.caption("Higher score = more anomalous (calibrate thresholds with data)")
                else:
                    st.info("ML model not found. Run `ml/train_baseline.py` to create it.")
            except Exception as _e:
                st.info("ML inference unavailable: install scikit-learn and train model.")
    except Exception:
        # Non-fatal UI error; continue rendering other widgets
        pass

    for subsys, params in config.SUBSYSTEM_PARAMETERS.items():
        st.subheader(subsys.replace("_", " ").title())

        subsystem_evals = fetch_latest_evals_for_params(selected_flight, params)

        cols = st.columns(len(params))
        for i, param in enumerate(params):
            with cols[i]:
                if param in subsystem_evals:
                    eval_data = subsystem_evals[param]
                    unit = "°C" if "temp" in param or "cht" in param or "egt" in param else \
                           "psi" if "pressure" in param else \
                           "L/h" if "fuel" in param else \
                           "g" if "vibration" in param else \
                           "V" if "battery" in param else ""
                    render_parameter_gauge(
                        param,
                        eval_data["actual"],
                        eval_data["expected"],
                        eval_data["status"],
                        unit,
                    )

    # Trend chart for worst parameter
    st.markdown("---")
    st.subheader("Trend Analysis")
    worst_subsys = min(subsys_health, key=subsys_health.get)
    worst_params = config.SUBSYSTEM_PARAMETERS.get(worst_subsys, [])
    if worst_params and not st.session_state.get("manual_snapshot_active", False):
        selected_param = st.selectbox("Select Parameter for Trend", worst_params)
        render_trend_chart(selected_flight, selected_param, telemetry["mission_time_s"])
    elif st.session_state.get("manual_snapshot_active", False):
        st.info("Manual snapshot mode is active; trend history is not available for custom injected values.")

    # Auto-refresh status
    st.caption("🔄 Live data refreshes automatically when the dashboard reruns")


def render_history_view():
    """Render historical flight analysis view."""
    st.header("Flight History & Analysis")

    flights = query_flights()
    if not flights:
        st.info("No complete flights available")
        return

    # Flight picker
    flight_options = [f"{f['flight_id']} ({f['climate_zone']}, {f['start_time'][:10]})" for f in flights]
    selected = st.selectbox("Select Flight", flight_options)
    selected_flight = selected.split(" ")[0]

    # Get flight duration
    duration = get_flight_duration(selected_flight)

    # Time scrubber
    mission_time_s = st.slider(
        "Mission Time",
        min_value=0.0,
        max_value=duration,
        value=duration,
        step=config.PACKET_INTERVAL_S,
        format="%.0f seconds",
    )

    # Get data at selected time
    telemetry = get_telemetry_at_time(selected_flight, mission_time_s)
    condition = get_flight_condition_at_time(selected_flight, mission_time_s)

    if not telemetry or not condition:
        st.error("No data at selected time")
        return

    subsys_health = json.loads(condition.get("subsystem_health_json", "{}"))

    # Render same as live view
    render_status_banner(condition["overall_status"], condition.get("icing_advisory", "LOW"))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mission Time", f"{telemetry['mission_time_s']/60:.1f} min")
    col2.metric("Phase", telemetry["phase"])
    col3.metric("Altitude", f"{telemetry['altitude_m']:.0f} m")
    col4.metric("RPM", f"{telemetry['rpm']:.0f}")

    st.markdown("---")
    st.subheader("Subsystem Health")
    render_subsystem_health(subsys_health)

    st.markdown("---")
    st.subheader("Engine Parameters")

    for subsys, params in config.SUBSYSTEM_PARAMETERS.items():
        st.subheader(subsys.replace("_", " ").title())

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT parameter, actual, expected, status FROM evaluations
            WHERE flight_id = ? AND parameter IN ({})
            AND mission_time_s <= ? 
            AND (flight_id, parameter, mission_time_s) IN (
                SELECT flight_id, parameter, MAX(mission_time_s)
                FROM evaluations
                WHERE flight_id = ? AND parameter IN ({}) AND mission_time_s <= ?
                GROUP BY parameter
            )
            """.format(",".join("?" * len(params)), ",".join("?" * len(params))),
            [selected_flight] + params + [mission_time_s, selected_flight] + params + [mission_time_s],
        )
        rows = cursor.fetchall()
        evals = {r[0]: {"actual": r[1], "expected": r[2], "status": r[3]} for r in rows}

        cols = st.columns(len(params))
        for i, param in enumerate(params):
            with cols[i]:
                if param in evals:
                    eval_data = evals[param]
                    unit = "°C" if "temp" in param or "cht" in param or "egt" in param else \
                           "psi" if "pressure" in param else \
                           "L/h" if "fuel" in param else \
                           "g" if "vibration" in param else \
                           "V" if "battery" in param else ""
                    render_parameter_gauge(
                        param,
                        eval_data["actual"],
                        eval_data["expected"],
                        eval_data["status"],
                        unit,
                    )


def render_maintenance_view():
    """Render maintenance advisory view."""
    st.header("Maintenance & Advisory")

    st.subheader("Environmental Advisories")

    flights = query_flights()
    if flights:
        selected = st.selectbox("Select Flight", [f"{f['flight_id']}" for f in flights])

        # Get latest condition
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT icing_advisory, fault_category FROM flight_condition WHERE flight_id = ? "
            "ORDER BY mission_time_s DESC LIMIT 1",
            (selected,),
        )
        result = cursor.fetchone()

        if result:
            icing, fault = result
            st.write(f"**Icing Risk:** {icing}")
            if fault:
                st.warning(f"**Fault Category:** {fault}")
        else:
            st.info("No condition data available")
    else:
        st.info("No flights available")


if __name__ == "__main__":
    main()
