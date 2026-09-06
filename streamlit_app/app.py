import streamlit as st
import requests
import pandas as pd
import time

# Configuration
BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="UAV Digital Twin Admin Console",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ UAV Engine Digital Twin Admin Console")

# Sidebar for Navigation (Streamlit multi-page handles this, but we can add status here)
st.sidebar.header("System Status")

def get_status():
    try:
        response = requests.get(f"{BACKEND_URL}/api/live/status", timeout=1)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

status = get_status()

if "error" in status:
    st.sidebar.error(f"Backend Unreachable: {status['error']}")
else:
    # Status badges in sidebar
    st.sidebar.metric("CAN Bus", status.get("can", "UNKNOWN"))
    st.sidebar.metric("PostgreSQL", status.get("postgresql", "UNKNOWN"))
    st.sidebar.metric("Backend", status.get("backend", "UNKNOWN"))
    st.sidebar.divider()
    st.sidebar.write(f"**Active Flight:** {status.get('active_flight', 'NONE')}")
    st.sidebar.write(f"**Flight Status:** {status.get('flight_status', 'IDLE')}")

# Main Overview Page
st.subheader("System Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Frames", status.get("total_frames_received", 0))
with col2:
    st.metric("Telemetry State", "STALE" if status.get("stale_telemetry") else "FRESH")
with col3:
    st.metric("Physics Engine", status.get("physics_engine", "UNKNOWN"))
with col4:
    st.metric("AI Engine", status.get("ai_engine", "UNKNOWN"))

st.divider()

# High Level Health
st.subheader("Engine Health Summary")
try:
    health_res = requests.get(f"{BACKEND_URL}/api/live/health", timeout=1).json()

    h_col1, h_col2, h_col3 = st.columns(3)
    with h_col1:
        st.metric("Engine Health", f"{health_res.get('engine_health', 0)}%")
    with h_col2:
        st.metric("Anomaly Score", f"{health_res.get('anomaly_score', 0)}%")
    with h_col3:
        st.metric("Current Fault", health_res.get('current_fault', 'NONE'))

    if health_res.get('current_fault') != "NONE":
        st.warning(f"⚠️ Alert: {health_res.get('current_fault')}")
except Exception as e:
    st.error(f"Could not fetch health data: {e}")

st.divider()

# Quick Controls
st.subheader("Quick Flight Controls")
c1, c2, c3 = st.columns(3)

with c1:
    with st.form("create_flight"):
        st.write("Create New Flight")
        label = st.text_input("Flight Label", "Test Flight")
        mission = st.selectbox("Mission Type", ["surveillance", "patrol", "transport", "test"])
        notes = st.text_area("Notes")
        if st.form_submit_button("Create"):
            res = requests.post(f"{BACKEND_URL}/api/flights", params={"label": label, "mission_type": mission, "notes": notes})
            if res.status_code == 200:
                st.success(f"Created: {res.json()['flight_id']}")
            else:
                st.error("Failed to create flight")

with c2:
    with st.form("start_flight"):
        st.write("Start Active Flight")
        f_id = st.text_input("Flight ID")
        if st.form_submit_button("Start"):
            if f_id:
                res = requests.post(f"{BACKEND_URL}/api/flights/{f_id}/start")
                if res.status_code == 200:
                    st.success(f"Flight {f_id} started!")
                else:
                    st.error("Failed to start")
            else:
                st.error("Flight ID required")

with c3:
    with st.form("stop_flight"):
        st.write("Stop Active Flight")
        if st.form_submit_button("Stop Now"):
            res = requests.post(f"{BACKEND_URL}/api/flights/{{flight_id}}/stop") # Note: This is generic, but recorder.stop_flight doesn't need ID if it's active.
            # Actually our API is /api/flights/{flight_id}/stop.
            # We should get active_flight from status.
            active_f = status.get("active_flight")
            if active_f and active_f != "NONE":
                res = requests.post(f"{BACKEND_URL}/api/flights/{active_f}/stop")
                if res.status_code == 200:
                    st.success(f"Flight {active_f} stopped!")
                else:
                    st.error("Failed to stop")
            else:
                st.error("No active flight to stop")

st.divider()

# Simulator Control
st.subheader("Simulator Control")
s1, s2, s3 = st.columns(3)
with s1:
    if st.button("🚀 Start Simulator"):
        requests.post(f"{BACKEND_URL}/api/simulator/start")
        st.info("Simulator start request sent")
with s2:
    if st.button("🛑 Stop Simulator"):
        requests.post(f"{BACKEND_URL}/api/simulator/stop")
        st.info("Simulator stop request sent")
with s3:
    if st.button("🔄 Check Status"):
        res = requests.get(f"{BACKEND_URL}/api/simulator/status").json()
        st.write(f"Running: {res.get('running')}")
