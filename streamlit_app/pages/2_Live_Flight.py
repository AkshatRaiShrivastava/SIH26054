"""
Streamlit Page 2 — Live Flight Monitoring.
"""

import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="Live Flight | UAV Digital Twin", page_icon="📡", layout="wide")

st.title("📡 Live Flight Telemetry & Physics Monitor")

# Initialize session state rolling buffer for charts
if "rolling_history" not in st.session_state:
    st.session_state.rolling_history = []

status = api_client.get_status()
active_flight = status.get("active_flight", "NONE")
flight_status = status.get("flight_status", "IDLE")

# Header Section: Flight Info
info_c1, info_c2, info_c3, info_c4, info_c5 = st.columns(5)
info_c1.metric("Flight ID", active_flight)
info_c2.metric("Flight Status", flight_status)
info_c3.metric("CAN Connection", status.get("can", "DISCONNECTED"))
info_c4.metric("Engine Health", f"{api_client.get_live_health().get('engine_health', 100)}%")
info_c5.metric("Anomaly Score", f"{api_client.get_live_health().get('anomaly_score', 0)}%")

st.divider()

# Fetch latest live data
telemetry = api_client.get_live_telemetry()
physics = api_client.get_live_physics()

if telemetry:
    timestamp = telemetry.get("timestamp", time.strftime("%H:%M:%S"))
    rpm = telemetry.get("rpm", 0)
    cht = telemetry.get("cht", 0.0)
    egt = telemetry.get("egt", 0.0)
    oil_p_kpa = telemetry.get("oil_pressure", 0.0)
    oil_p_psi = oil_p_kpa * 0.145038
    oil_t = telemetry.get("oil_temperature", 0.0)
    fuel_f = telemetry.get("fuel_flow", 0.0)
    vib_mms = telemetry.get("vibration", 0.0)
    vib_g = vib_mms / 9.81
    batt_v = telemetry.get("battery_voltage", 0.0)

    # Append to rolling history (max 60 points)
    st.session_state.rolling_history.append({
        "time": timestamp,
        "rpm": rpm,
        "cht": cht,
        "egt": egt,
        "oil_p": oil_p_psi,
        "oil_t": oil_t,
        "fuel_f": fuel_f,
        "vib": vib_g,
        "batt": batt_v,
    })
    if len(st.session_state.rolling_history) > 60:
        st.session_state.rolling_history.pop(0)

# Section B: Current Engine Telemetry Metrics
st.subheader("⚡ Live Engine Telemetry Snapshots")
m1, m2, m3, m4, m5, m6, m7, m8 = st.columns(8)
m1.metric("RPM", f"{telemetry.get('rpm', 0):.0f} rpm")
m2.metric("CHT", f"{telemetry.get('cht', 0.0):.1f} °C")
m3.metric("EGT", f"{telemetry.get('egt', 0.0):.1f} °C")
m4.metric("Oil Press", f"{telemetry.get('oil_pressure', 0.0) * 0.145038:.1f} psi")
m5.metric("Oil Temp", f"{telemetry.get('oil_temperature', 0.0):.1f} °C")
m6.metric("Fuel Flow", f"{telemetry.get('fuel_flow', 0.0):.1f} L/h")
m7.metric("Vibration", f"{telemetry.get('vibration', 0.0) / 9.81:.2f} g")
m8.metric("Battery", f"{telemetry.get('battery_voltage', 0.0):.1f} V")

st.divider()

# Section C: Physics Comparison Table
st.subheader("🔬 Physics Model Evaluation (Actual vs Expected)")

physics_rows = []
signal_display_names = {
    "rpm": "RPM (rpm)",
    "cht_c": "CHT (°C)",
    "egt_c": "EGT (°C)",
    "oil_pressure_psi": "Oil Pressure (psi)",
    "oil_temp_c": "Oil Temperature (°C)",
    "fuel_flow_lph": "Fuel Flow (L/h)",
    "vibration_g": "Vibration (g)",
    "battery_v": "Battery Voltage (V)",
}

for key, name in signal_display_names.items():
    if key in physics:
        p_data = physics[key]
        act = p_data.get("actual", 0.0)
        exp = p_data.get("expected", 0.0)
        res = p_data.get("residual", 0.0)
        res_p = p_data.get("residual_pct", 0.0)
        status_txt = p_data.get("status", "normal").upper()
    else:
        act, exp, res, res_p, status_txt = 0.0, 0.0, 0.0, 0.0, "PENDING"

    physics_rows.append({
        "Signal": name,
        "Actual": f"{act:.2f}",
        "Expected": f"{exp:.2f}",
        "Residual": f"{res:+.2f}",
        "Residual %": f"{res_p:+.2f}%",
        "Status": status_txt,
    })

p_df = pd.DataFrame(physics_rows)
st.dataframe(p_df, use_container_width=True)

st.divider()

# Section D: Bounded Rolling Time-Series Charts
st.subheader("📈 Real-Time Engine Parameter Trends")

if st.session_state.rolling_history:
    df_roll = pd.DataFrame(st.session_state.rolling_history)

    c1, c2 = st.columns(2)
    with c1:
        fig_rpm = go.Figure()
        fig_rpm.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["rpm"], mode="lines+markers", name="RPM", line=dict(color="#4ea8de", width=2)))
        fig_rpm.update_layout(title="RPM vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_rpm, use_container_width=True)

        fig_egt = go.Figure()
        fig_egt.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["egt"], mode="lines+markers", name="EGT", line=dict(color="#ff4d6d", width=2)))
        fig_egt.update_layout(title="EGT (°C) vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_egt, use_container_width=True)

        fig_oilp = go.Figure()
        fig_oilp.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["oil_p"], mode="lines+markers", name="Oil Press", line=dict(color="#ffb703", width=2)))
        fig_oilp.update_layout(title="Oil Pressure (psi) vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_oilp, use_container_width=True)

    with c2:
        fig_cht = go.Figure()
        fig_cht.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["cht"], mode="lines+markers", name="CHT", line=dict(color="#70e000", width=2)))
        fig_cht.update_layout(title="CHT (°C) vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_cht, use_container_width=True)

        fig_ff = go.Figure()
        fig_ff.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["fuel_f"], mode="lines+markers", name="Fuel Flow", line=dict(color="#3a86ff", width=2)))
        fig_ff.update_layout(title="Fuel Flow (L/h) vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_ff, use_container_width=True)

        fig_vib = go.Figure()
        fig_vib.add_trace(go.Scatter(x=df_roll["time"], y=df_roll["vib"], mode="lines+markers", name="Vibration", line=dict(color="#8338ec", width=2)))
        fig_vib.update_layout(title="Vibration (g) vs Time", template="plotly_dark", height=260, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_vib, use_container_width=True)

# Controlled Auto-Refresh toggle
auto_refresh = st.checkbox("Auto-refresh live telemetry (1s)", value=True)
if auto_refresh:
    time.sleep(1.0)
    st.rerun()
