"""
Streamlit Page 4 — Flight Session Management & Simulator Controls.
"""

import streamlit as st
import pandas as pd
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="Flight Management | UAV Digital Twin", page_icon="⚙️", layout="wide")

st.title("⚙️ Flight Session & Simulator Control Console")
st.caption("Admin control interface for creating flight sessions, starting/stopping telemetry recording, and orchestrating CAN engine simulations.")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("➕ Create & Manage Flight Session")

    with st.form("create_flight_form"):
        label_in = st.text_input("Flight Label / Name", value="Surveillance Flight Alpha")
        mission_in = st.selectbox("Mission Type", ["surveillance", "endurance", "high_altitude", "dynamic_throttle"])
        notes_in = st.text_area("Flight Notes / Objectives", value="Routine surveillance flight with physics layer residual tracking.")
        submit_btn = st.form_submit_button("🚀 CREATE NEW FLIGHT", use_container_width=True)

        if submit_btn:
            res = api_client.create_flight(label=label_in, mission_type=mission_in, notes=notes_in)
            if "flight_id" in res:
                st.success(f"Successfully Created Flight ID: **{res['flight_id']}** (Status: CREATED)")
            else:
                st.error(f"Failed to create flight: {res.get('error', 'Unknown error')}")

    st.divider()

    status_info = api_client.get_status()
    act_flt = status_info.get("active_flight", "NONE")
    flt_state = status_info.get("flight_status", "IDLE")

    st.markdown(f"**Current Active Flight:** `{act_flt}`")
    st.markdown(f"**Current Status:** `{flt_state}`")

    # Session Control Buttons
    c_btn1, c_btn2, c_btn3 = st.columns(3)
    with c_btn1:
        if st.button("▶️ START FLIGHT", use_container_width=True):
            if act_flt != "NONE":
                res = api_client.start_flight(act_flt)
                st.success(f"Flight {act_flt} set to RUNNING!")
                st.rerun()
            else:
                st.warning("Please select a flight to start.")

    with c_btn2:
        if st.button("⏹️ COMPLETE FLIGHT", use_container_width=True):
            if act_flt != "NONE":
                res = api_client.stop_flight(act_flt)
                st.info(f"Flight {act_flt} COMPLETED!")
                st.rerun()

    with c_btn3:
        if st.button("🚨 ABORT FLIGHT", use_container_width=True):
            if act_flt != "NONE":
                res = api_client.stop_flight(act_flt)
                st.error(f"Flight {act_flt} ABORTED!")
                st.rerun()

with col_right:
    st.subheader("🤖 CAN Simulator Orchestration")
    st.info("ℹ️ Note: These controls operate the CAN engine physics simulator process. They do NOT send commands to a physical aircraft.")

    sim_stat = api_client.get_simulator_status()
    is_sim_running = sim_stat.get("running", False)

    if is_sim_running:
        st.success(f"🟢 CAN Simulator is RUNNING (PID: {sim_stat.get('pid')})")
    else:
        st.warning("🔴 CAN Simulator is STOPPED")

    with st.form("sim_control_form"):
        sim_mission = st.selectbox("Simulation Mission Profile", ["surveillance", "endurance"])
        sim_speed = st.slider("Simulation Speed Multiplier", min_value=0.5, max_value=10.0, value=1.0, step=0.5)
        sim_fault = st.selectbox(
            "Fault Injection Scenario (Optional)",
            ["None", "injector_degradation:0.8", "cooling_degradation:0.5", "lubrication_degradation:0.7"],
        )

        sim_start_btn = st.form_submit_button("▶️ LAUNCH SIMULATOR PROCESS", use_container_width=True)
        if sim_start_btn:
            fault_arg = "" if sim_fault == "None" else sim_fault
            res = api_client.start_simulator(mission=sim_mission, speed=sim_speed, fault=fault_arg)
            if res.get("status") == "STARTED":
                st.success(f"Simulator launched successfully (PID: {res.get('pid')})!")
                st.rerun()
            elif res.get("status") == "ALREADY_RUNNING":
                st.info(f"Simulator is already running (PID: {res.get('pid')}).")
            else:
                st.error(f"Failed to start simulator: {res.get('message')}")

    if st.button("⏹️ TERMINATE SIMULATOR PROCESS", use_container_width=True):
        res = api_client.stop_simulator()
        st.info("Simulator process terminated.")
        st.rerun()

st.divider()

# Flight Log Table
st.subheader("📋 All Registered Flight Sessions")
flights = api_client.get_flights()
if flights:
    df = pd.DataFrame(flights)
    st.dataframe(df, use_container_width=True)

    selected_flt_id = st.selectbox("Select Flight to Arm or Set Active", [f["flight_id"] for f in flights])
    if st.button("📌 Set Active Flight"):
        api_client.start_flight(selected_flt_id)
        st.success(f"Flight {selected_flt_id} is now ACTIVE!")
        st.rerun()
else:
    st.info("No flight records found in PostgreSQL.")
