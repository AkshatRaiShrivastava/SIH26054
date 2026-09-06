import streamlit as st
import requests
import pandas as pd
import numpy as np
import websocket
import json
import time
from datetime import datetime

BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/live"

st.set_page_config(page_title="Live Flight Monitor", layout="wide")

st.title("🛰️ Live Flight Monitor")

# Layout
col_telemetry, col_physics = st.columns([2, 1])

with col_telemetry:
    st.subheader("Real-time Telemetry")
    # Placeholders for charts
    chart_placeholder = st.empty()
    metric_placeholder = st.empty()

with col_physics:
    st.subheader("Physics Residuals")
    physics_placeholder = st.empty()

# State for rolling data
if "telemetry_history" not in st.session_state:
    st.session_state.telemetry_history = pd.DataFrame()

# Connection logic
def start_live_stream():
    try:
        ws = websocket.create_connection(WS_URL)

        # To avoid blocking Streamlit forever, we'll read for a while
        # or use a specific condition. In a real app, we'd use a
        # separate thread or a custom component.
        # For this demonstrator, we'll process a batch of messages.

        while True:
            result = ws.recv()
            data = json.loads(result)

            # 1. Process Telemetry
            tel = data.get("telemetry", {})
            if tel:
                # Convert to DataFrame row
                new_row = pd.DataFrame([tel])
                st.session_state.telemetry_history = pd.concat(
                    [st.session_state.telemetry_history, new_row]
                ).tail(100) # Keep last 100 samples

                # Update metrics
                with metric_placeholder.container():
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("RPM", f"{tel.get('rpm', 0):.0f}")
                    m2.metric("CHT", f"{tel.get('cht', 0):.1f}°C")
                    m3.metric("EGT", f"{tel.get('egt', 0):.1f}°C")
                    m4.metric("Oil Press", f"{tel.get('oil_pressure', 0):.1f} kPa")

                # Update Chart
                if not st.session_state.telemetry_history.empty:
                    # Plotting key signals
                    cols_to_plot = ['rpm', 'cht', 'egt', 'oil_pressure']
                    available_cols = [c for c in cols_to_plot if c in st.session_state.telemetry_history.columns]
                    chart_placeholder.line_chart(st.session_state.telemetry_history[available_cols])

            # 2. Process Physics
            phys = data.get("physics", {})
            if phys:
                phys_data = []
                for sig, vals in phys.items():
                    phys_data.append({
                        "Signal": sig,
                        "Actual": vals.get("actual"),
                        "Expected": vals.get("expected"),
                        "Residual %": vals.get("residual_pct"),
                        "Status": vals.get("status")
                    })
                df_phys = pd.DataFrame(phys_data)
                with physics_placeholder.container():
                    st.table(df_phys)

            # Small sleep to prevent CPU pegging
            time.sleep(0.1)

    except Exception as e:
        st.error(f"WebSocket Error: {e}")

if st.button("Start Live Stream"):
    start_live_stream()
else:
    st.info("Click 'Start Live Stream' to begin monitoring.")
