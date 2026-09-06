"""
Streamlit Page 1 — Admin Overview.
"""

import streamlit as st
import pandas as pd
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="Overview | UAV Digital Twin", page_icon="🎛️", layout="wide")

st.title("🎛️ Digital Twin System Overview")
st.caption("High-level system status, active session telemetry, and baseline health indicators")

# System Connection Cards
status = api_client.get_status()
health_info = api_client.get_live_health()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    can_val = status.get("can", "DISCONNECTED")
    st.metric("CAN Interface (vcan0)", can_val, delta="Active" if can_val == "CONNECTED" else "Inactive")
with col2:
    backend_val = status.get("backend", "OFFLINE")
    st.metric("Backend Service", backend_val)
with col3:
    db_val = status.get("postgresql", "DISCONNECTED")
    st.metric("PostgreSQL Database", db_val)
with col4:
    phys_val = status.get("physics_engine", "UNAVAILABLE")
    st.metric("Physics Model Layer", phys_val)
with col5:
    ai_val = status.get("ai_engine", "MODEL NOT ACTIVE")
    st.metric("AI Health Pipeline", ai_val)

st.divider()

# Active Flight & High-Level Health Metrics
c_left, c_right = st.columns([1, 1])

with c_left:
    st.subheader("✈️ Active Flight Session")
    act_flight = status.get("active_flight", "NONE")
    flt_stat = status.get("flight_status", "IDLE")

    st.markdown(f"**Flight ID:** `{act_flight}`")
    st.markdown(f"**Flight Status:** `{flt_stat}`")
    st.markdown(f"**Total Telemetry Frames Ingested:** `{status.get('total_frames_received', 0)}`")

    if status.get("stale_telemetry"):
        st.warning("⚠️ Telemetry stream is stale or CAN simulator is paused.")

with c_right:
    st.subheader("🩺 Engine Diagnostic Summary")
    eng_health = health_info.get("engine_health", 100.0)
    anom_score = health_info.get("anomaly_score", 0.0)
    fault_txt = health_info.get("current_fault", "NONE")
    rul_txt = health_info.get("rul", "Model not active")

    h_col1, h_col2 = st.columns(2)
    h_col1.metric("Engine Health", f"{eng_health}%", delta=f"{eng_health - 100:.1f}%")
    h_col2.metric("Anomaly Score", f"{anom_score}%")

    st.markdown(f"**Detected Fault:** `{fault_txt}`")
    st.markdown(f"**Estimated RUL:** `{rul_txt}`")

st.divider()

# Quick Overview of Recent Flights
st.subheader("📋 Recent Flight Log Summary")
flights = api_client.get_flights()
if flights:
    df_f = pd.DataFrame(flights)
    st.dataframe(
        df_f[["flight_id", "status", "created_at", "started_at", "ended_at", "sample_count", "label"]],
        use_container_width=True,
    )
else:
    st.info("No flight records found in PostgreSQL database. Go to 'Flight Management' to create a new flight.")
