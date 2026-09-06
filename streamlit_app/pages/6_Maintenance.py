"""
Streamlit Page 6 — Maintenance Advisory & Component Condition Console.
"""

import streamlit as st
import pandas as pd
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="Maintenance | UAV Digital Twin", page_icon="🛠️", layout="wide")

st.title("🛠️ Maintenance Advisory & Component Health Console")
st.caption("Engineering advisory service monitoring physics model residual trends, thermal stress, and vibration signatures")

st.warning("⚠️ Disclaimer: Prototype advisory system for engineering research — All recommendations require certified maintenance validation before aircraft service.")

status = api_client.get_status()
active_flight = status.get("active_flight", "NONE")

# Section A: Subsystem Component Health Breakdown
st.subheader("⚙️ Engine Subsystem Health Status")

physics = api_client.get_live_physics()

def compute_comp_health(signal_keys):
    if not physics:
        return 100.0, "NORMAL"
    max_res = 0.0
    for k in signal_keys:
        if k in physics:
            res_p = abs(physics[k].get("residual_pct", 0.0))
            if res_p > max_res:
                max_res = res_p
    h = max(0.0, 100.0 - max_res * 2.5)
    st_val = "NORMAL" if h >= 85 else ("INSPECT" if h >= 65 else "CRITICAL")
    return round(h, 1), st_val

comp_data = [
    {"Component": "Engine Core", "Health Score": f"{compute_comp_health(['rpm'])[0]}%", "Status": compute_comp_health(['rpm'])[1]},
    {"Component": "Fuel Injector & Combustion", "Health Score": f"{compute_comp_health(['egt_c', 'fuel_flow_lph'])[0]}%", "Status": compute_comp_health(['egt_c', 'fuel_flow_lph'])[1]},
    {"Component": "Lubrication System", "Health Score": f"{compute_comp_health(['oil_pressure_psi', 'oil_temp_c'])[0]}%", "Status": compute_comp_health(['oil_pressure_psi', 'oil_temp_c'])[1]},
    {"Component": "Cooling System", "Health Score": f"{compute_comp_health(['cht_c'])[0]}%", "Status": compute_comp_health(['cht_c'])[1]},
    {"Component": "Electrical System", "Health Score": f"{compute_comp_health(['battery_v'])[0]}%", "Status": compute_comp_health(['battery_v'])[1]},
    {"Component": "Mechanical / Vibration Assembly", "Health Score": f"{compute_comp_health(['vibration_g'])[0]}%", "Status": compute_comp_health(['vibration_g'])[1]},
]

st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

st.divider()

# Section B: Active Maintenance Recommendations
st.subheader("📋 Active Maintenance Advisories & Engineering Recommendations")

maint_list = api_client.get_live_maintenance()

if not maint_list and active_flight != "NONE":
    maint_list = api_client.get_flight_maintenance(active_flight)

if maint_list:
    for m in maint_list:
        prio = m.get("priority", "LOW")
        comp = m.get("component", "Engine")
        reason = m.get("reason", "")
        evidence = m.get("evidence", "")
        recom = m.get("recommendation", "")
        due = m.get("due_hours", 50.0)

        if prio == "HIGH":
            st.error(f"🔴 **Priority: {prio}** | Component: **{comp}** (Due within {due} hrs)")
        elif prio == "MEDIUM":
            st.warning(f"🟡 **Priority: {prio}** | Component: **{comp}** (Due within {due} hrs)")
        else:
            st.success(f"🟢 **Priority: {prio}** | Component: **{comp}** (Routine)")

        c_a, c_b = st.columns([1, 1])
        with c_a:
            st.markdown(f"**Reason:** {reason}")
            st.markdown(f"**Evidence:** {evidence}")
        with c_b:
            st.markdown(f"**Recommended Action:** {recom}")
            st.markdown(f"**Status:** `{m.get('status', 'OPEN')}`")
        st.divider()
else:
    st.info("No active maintenance advisories. Monitored engine signals are within nominal parameters.")

# Section C: Maintenance History Log
st.subheader("📜 Historical Maintenance Log")
flights = api_client.get_flights()
if flights:
    selected_f = st.selectbox("Select Flight to View Historical Maintenance Records", [f["flight_id"] for f in flights])
    if selected_f:
        hist_records = api_client.get_flight_maintenance(selected_f)
        if hist_records:
            st.dataframe(pd.DataFrame(hist_records), use_container_width=True)
        else:
            st.info(f"No recorded maintenance actions for flight `{selected_f}`.")
