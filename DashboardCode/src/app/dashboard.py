"""
Digital Twin Dashboard — Integrated View for UAV Telemetry and Physics.

Shows:
- Live UAV telemetry with parameter gauges and health status
- Historical flight data with time scrubber
- Environmental advisories (icing risk, corrosion)
- Subsystem health breakdown
"""

import os
import sys
import time
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from collections import defaultdict
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.utils import config
from src.database import database
from src.core.physics_layer import PhysicsEvaluator
from src.core.environmental_physics import EnvironmentalPhysics

# ============================================================================
# PAGE CONFIG AND LAYOUT
# ============================================================================

st.set_page_config(
    page_title="UAV Digital Twin Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .metric-box { background: #f0f2f6; padding: 10px; border-radius: 5px; margin: 5px; }
        .status-normal { color: #28a745; font-weight: bold; font-size: 1.2em; }
        .status-caution { color: #ffc107; font-weight: bold; font-size: 1.2em; }
        .status-critical { color: #dc3545; font-weight: bold; font-size: 1.2em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# DATABASE UTILITIES (PostgreSQL)
# ============================================================================

def query_flights():
    """Get all live or completed flights."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT flight_id, start_time, climate_zone, fault_injected "
                "FROM flights WHERE status IN ('in_progress', 'complete') ORDER BY start_time DESC"
            )
            rows = cur.fetchall()
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
        database.close_connection(conn)

def get_latest_telemetry(flight_id: str):
    """Get the most recent telemetry packet for a flight."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM telemetry WHERE flight_id = %s ORDER BY mission_time_s DESC LIMIT 1",
                (flight_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            col_names = [desc[0] for desc in cur.description]
            return dict(zip(col_names, row))
    finally:
        database.close_connection(conn)

def get_latest_flight_condition(flight_id: str):
    """Get the most recent flight condition for a flight."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM flight_condition WHERE flight_id = %s ORDER BY mission_time_s DESC LIMIT 1",
                (flight_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            col_names = [desc[0] for desc in cur.description]
            return dict(zip(col_names, row))
    finally:
        database.close_connection(conn)

def get_telemetry_at_time(flight_id: str, mission_time_s: float):
    """Get telemetry at or nearest to a specific mission time."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM telemetry
                WHERE flight_id = %s AND mission_time_s <= %s
                ORDER BY mission_time_s DESC LIMIT 1
                """,
                (flight_id, mission_time_s),
            )
            row = cur.fetchone()
            if not row:
                return None
            col_names = [desc[0] for desc in cur.description]
            return dict(zip(col_names, row))
    finally:
        database.close_connection(conn)

def get_flight_condition_at_time(flight_id: str, mission_time_s: float):
    """Get flight condition at or nearest to a specific mission time."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM flight_condition
                WHERE flight_id = %s AND mission_time_s <= %s
                ORDER BY mission_time_s DESC LIMIT 1
                """,
                (flight_id, mission_time_s),
            )
            row = cur.fetchone()
            if not row:
                return None
            col_names = [desc[0] for desc in cur.description]
            return dict(zip(col_names, row))
    finally:
        database.close_connection(conn)

def get_flight_duration(flight_id: str):
    """Get total mission time for a flight."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(mission_time_s) FROM telemetry WHERE flight_id = %s",
                (flight_id,),
            )
            result = cur.fetchone()
            return result[0] if result and result[0] else 0
    finally:
        database.close_connection(conn)

def get_trend_data(flight_id: str, parameter: str, mission_time_start: float):
    """Get trend data for a parameter over last N minutes."""
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_time_s, actual, expected, status
                FROM evaluations
                WHERE flight_id = %s AND parameter = %s AND mission_time_s >= %s
                ORDER BY mission_time_s ASC
                """,
                (flight_id, parameter, mission_time_start),
            )
            rows = cur.fetchall()
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
        database.close_connection(conn)

def fetch_latest_evals_for_params(flight_id: str, params: list[str]):
    """Return the latest evaluation row for each requested parameter."""
    if not params:
        return {}

    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            # PostgreSQL doesn't support '?' placeholders, use '%s'
            placeholders = ", ".join("%s" for _ in params)
            query = f"""
                SELECT parameter, actual, expected, status
                FROM evaluations
                WHERE flight_id = %s AND parameter IN ({placeholders})
                AND mission_time_s = (
                    SELECT MAX(mission_time_s)
                    FROM evaluations e2
                    WHERE e2.flight_id = evaluations.flight_id
                      AND e2.parameter = evaluations.parameter
                )
            """
            cur.execute(query, [flight_id, *params])
            rows = cur.fetchall()
            return {r[0]: {"actual": r[1], "expected": r[2], "status": r[3]} for r in rows}
    finally:
        database.close_connection(conn)

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_status_banner(status: str, icing_risk: str = "LOW"):
    """Render top banner with overall status and icing advisory."""
    col1, col2 = st.columns([3, 1])

    with col1:
        if status == "normal":
            st.markdown("<div class='status-normal'>🟢 NORMAL - All systems nominal</div>", unsafe_allow_html=True)
        elif status == "caution":
            st.markdown("<div class='status-caution'>🟡 CAUTION - Investigate anomalies</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-critical'>🔴 CRITICAL - Immediate attention required</div>", unsafe_allow_html=True)

    with col2:
        if icing_risk == "HIGH":
            st.markdown("<div class='status-critical'>❄️ HIGH ICING RISK</div>", unsafe_allow_html=True)
        elif icing_risk == "MODERATE":
            st.markdown("<div class='status-caution'>❄️ MODERATE ICING RISK</div>", unsafe_allow_html=True)

def render_parameter_gauge(param_name: str, actual: float, expected: float, status: str, unit: str):
    """Render a single parameter gauge."""
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
                    <h4 style="margin:0">{subsys.replace('_', ' ').title()}</h4>
                    <h2 style="margin:0">{score:.0f}%</h2>
                </div>
                """,
                unsafe_allow_html=True,
            )

def render_trend_chart(flight_id: str, parameter: str, mission_time_end: float):
    """Render trend chart for a parameter."""
    mission_time_start = max(0, mission_time_end - 1800)
    trend_data = get_trend_data(flight_id, parameter, mission_time_start)

    if not trend_data:
        st.info(f"No trend data available for {parameter}")
        return

    df = pd.DataFrame(trend_data)
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["time"] / 60,
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
    st.session_state.setdefault("live_feed_enabled", True)
    refresh_interval_s = st.sidebar.slider("Auto-refresh every", 2, 30, 5, 1)
    if st.session_state.get("live_feed_enabled", True):
        st_autorefresh(interval=refresh_interval_s * 1000, key="dashboard_autorefresh")

    st.title("✈️ UAV Digital Twin Dashboard")
    st.markdown("---")

    mode = st.sidebar.radio("Select View", ["Live Flight", "Flight History", "Maintenance"])

    if mode == "Live Flight":
        render_live_view()
    elif mode == "Flight History":
        render_history_view()
    else:
        render_maintenance_view()

def render_live_view():
    """Render live flight monitoring view."""
    st.header("Live Flight Monitoring")

    flights = query_flights()
    if not flights:
        st.info("No flights found in database. Please start the CAN Simulator and Backend service.")
        return

    # Try to find an in-progress flight
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT flight_id FROM flights WHERE status = 'in_progress' ORDER BY start_time DESC LIMIT 1"
            )
            in_progress = cur.fetchone()
    finally:
        database.close_connection(conn)

    if in_progress:
        selected_flight = in_progress[0]
        st.info(f"🔴 Live: {selected_flight}")
    else:
        flight_options = [f"{f['flight_id']} ({f['climate_zone']})" for f in flights]
        selected = st.selectbox("Select Flight", flight_options)
        selected_flight = selected.split(" ")[0]

    # Get latest data
    telemetry = get_latest_telemetry(selected_flight)
    condition = get_latest_flight_condition(selected_flight)

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

    # Parameter gauges
    st.subheader("Engine Parameters")
    for subsys, params in config.SUBSYSTEM_PARAMETERS.items():
        st.subheader(subsys.replace("_", " ").title())
        subsystem_evals = fetch_latest_evals_for_params(selected_flight, params)
        cols = st.columns(len(params))
        for i, param in enumerate(params):
            with cols[i]:
                if param in subsystem_evals:
                    eval_data = subsystem_evals[param]
                    unit = "°C" if any(x in param for x in ["temp", "cht", "egt"]) else \
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

    st.markdown("---")
    st.subheader("Trend Analysis")
    # Find parameter with worst status
    worst_param = None
    worst_score = 100
    for subsys, params in config.SUBSYSTEM_PARAMETERS.items():
        for p in params:
            eval_data = fetch_latest_evals_for_params(selected_flight, [p]).get(p)
            if eval_data and eval_data["status"] == "critical":
                worst_param = p
                break

    if not worst_param:
        # Default to RPM if nothing critical
        worst_param = "rpm"

    render_trend_chart(selected_flight, worst_param, telemetry["mission_time_s"])

def render_history_view():
    """Render historical flight analysis view."""
    st.header("Flight History & Analysis")

    flights = query_flights()
    if not flights:
        st.info("No complete flights available")
        return

    flight_options = [f"{f['flight_id']} ({f['climate_zone']}, {f['start_time'][:10]})" for f in flights]
    selected = st.selectbox("Select Flight", flight_options)
    selected_flight = selected.split(" ")[0]

    duration = get_flight_duration(selected_flight)
    mission_time_s = st.slider(
        "Mission Time",
        min_value=0.0,
        max_value=duration,
        value=duration,
        step=config.PACKET_INTERVAL_S,
        format="%.0f seconds",
    )

    telemetry = get_telemetry_at_time(selected_flight, mission_time_s)
    condition = get_flight_condition_at_time(selected_flight, mission_time_s)

    if not telemetry or not condition:
        st.error("No data at selected time")
        return

    subsys_health = json.loads(condition.get("subsystem_health_json", "{}"))
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

        # In history view, we just fetch evaluations for the specific flight and time
        conn = database.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT parameter, actual, expected, status FROM evaluations
                    WHERE flight_id = %s AND parameter IN (%s)
                    AND mission_time_s <= %s
                    ORDER BY mission_time_s DESC
                    """ % ("%s," * (len(params)-1) + "%s"),
                    [selected_flight] + params + [mission_time_s]
                )
                # This query is tricky with IN and ordered time.
                # Let's simplify: fetch all evals for this time and flight.
                cur.execute(
                    "SELECT parameter, actual, expected, status FROM evaluations WHERE flight_id = %s AND mission_time_s = %s",
                    (selected_flight, telemetry["mission_time_s"])
                )
                rows = cur.fetchall()
                evals = {r[0]: {"actual": r[1], "expected": r[2], "status": r[3]} for r in rows}
        finally:
            database.close_connection(conn)

        cols = st.columns(len(params))
        for i, param in enumerate(params):
            with cols[i]:
                if param in evals:
                    eval_data = evals[param]
                    unit = "°C" if any(x in param for x in ["temp", "cht", "egt"]) else \
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

    st.subheader("Fleet Health Overview")

    # Corrosion and maintenance are tracked per airframe
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT airframe_id, corrosion_index, last_updated FROM corrosion_tracking")
            corrosion_data = cur.fetchall()

            if corrosion_data:
                df_corr = pd.DataFrame(corrosion_data, columns=["Airframe", "Corrosion Index", "Last Updated"])
                st.table(df_corr)

                # Highlighting high corrosion
                high_corr = df_corr[df_corr["Corrosion Index"] > 50]
                if not high_corr.empty:
                    st.warning(f"⚠️ {len(high_corr)} airframes exceed maintenance threshold (Index > 50)")
            else:
                st.info("No corrosion tracking data available.")
    finally:
        database.close_connection(conn)

    st.markdown("---")
    st.subheader("Recent Flight Advisories")
    flights = query_flights()
    if flights:
        selected = st.selectbox("Select Flight", [f["flight_id"] for f in flights])
        conn = database.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT icing_advisory, fault_category FROM flight_condition WHERE flight_id = %s "
                    "ORDER BY mission_time_s DESC LIMIT 1",
                    (selected,),
                )
                result = cur.fetchone()
                if result:
                    icing, fault = result
                    st.write(f"**Icing Risk:** {icing}")
                    if fault:
                        st.warning(f"**Fault Category:** {fault}")
                else:
                    st.info("No condition data available")
        finally:
            database.close_connection(conn)
    else:
        st.info("No flights available")

if __name__ == "__main__":
    main()
