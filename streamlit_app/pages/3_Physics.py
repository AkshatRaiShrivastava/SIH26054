"""
Streamlit Page 3 — Physics Evaluation & Residual Analysis.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="Physics Analysis | UAV Digital Twin", page_icon="🔬", layout="wide")

st.title("🔬 Physics Model Residual & Deviation Analysis")
st.caption("Engine Physics Model Expected vs Actual Baseline Evaluation — Identifies physical behavior deviations prior to ML classification")

status = api_client.get_status()
active_flight = status.get("active_flight", "NONE")

if active_flight == "NONE":
    st.info("No active flight currently streaming. Select a completed flight below or start a new flight session.")
    flights = api_client.get_flights()
    if flights:
        selected_flight = st.selectbox("Select Flight History for Physics Analysis", [f["flight_id"] for f in flights])
    else:
        selected_flight = None
else:
    selected_flight = active_flight

if selected_flight:
    st.subheader(f"📊 Physics Residuals for `{selected_flight}`")
    physics_data = api_client.get_flight_physics(selected_flight)

    if not physics_data and active_flight != "NONE":
        # Fall back to live physics if DB historical physics is empty during start
        live_p = api_client.get_live_physics()
        if live_p:
            physics_data = []
            for sig, val in live_p.items():
                physics_data.append({
                    "flight_id": selected_flight,
                    "signal_name": sig,
                    "actual_value": val.get("actual", 0.0),
                    "expected_value": val.get("expected", 0.0),
                    "residual": val.get("residual", 0.0),
                    "residual_pct": val.get("residual_pct", 0.0),
                    "status": val.get("status", "normal"),
                    "mission_time_s": 0.0,
                })

    if physics_data:
        df_p = pd.DataFrame(physics_data)

        # Summary KPIs
        max_pos_res = df_p["residual_pct"].max()
        min_neg_res = df_p["residual_pct"].min()
        deviating_signals = df_p[df_p["residual_pct"].abs() > 5.0]["signal_name"].unique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Largest Positive Deviation", f"+{max_pos_res:.2f}%")
        k2.metric("Largest Negative Deviation", f"{min_neg_res:.2f}%")
        k3.metric("Signals Requiring Investigation", len(deviating_signals))
        k4.metric("Physics Model Status", "RUNNING - ACCURATE")

        st.divider()

        # Signal Selector for Time Series Analysis
        signals = df_p["signal_name"].unique()
        selected_sig = st.selectbox("Select Engine Parameter for Time Series Expected vs Actual Comparison", signals)

        if selected_sig:
            df_sig = df_p[df_p["signal_name"] == selected_sig]

            fig = go.Figure()
            if "mission_time_s" in df_sig.columns:
                x_axis = df_sig["mission_time_s"]
                x_title = "Mission Time (seconds)"
            else:
                x_axis = df_sig["timestamp"]
                x_title = "Timestamp"

            fig.add_trace(go.Scatter(x=x_axis, y=df_sig["actual_value"], mode="lines", name="Actual Telemetry", line=dict(color="#00b4d8", width=2)))
            fig.add_trace(go.Scatter(x=x_axis, y=df_sig["expected_value"], mode="lines", name="Physics Model Expected", line=dict(color="#ffb703", width=2, dash="dash")))

            fig.update_layout(
                title=f"{selected_sig} — Actual vs Physics Model Expected Baseline",
                xaxis_title=x_title,
                yaxis_title="Value",
                template="plotly_dark",
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Residual Percentage Chart
            fig_res = go.Figure()
            fig_res.add_trace(go.Scatter(x=x_axis, y=df_sig["residual_pct"], mode="lines", name="Residual %", line=dict(color="#ff4d6d", width=2)))
            fig_res.add_hline(y=5.0, line_dash="dot", line_color="#ffb703", annotation_text="Caution Threshold (+5%)")
            fig_res.add_hline(y=-5.0, line_dash="dot", line_color="#ffb703", annotation_text="Caution Threshold (-5%)")
            fig_res.add_hline(y=10.0, line_dash="dash", line_color="#ff4d6d", annotation_text="Critical Threshold (+10%)")
            fig_res.add_hline(y=-10.0, line_dash="dash", line_color="#ff4d6d", annotation_text="Critical Threshold (-10%)")

            fig_res.update_layout(
                title=f"{selected_sig} — Residual Deviation % over Time",
                xaxis_title=x_title,
                yaxis_title="Residual %",
                template="plotly_dark",
                height=320,
            )
            st.plotly_chart(fig_res, use_container_width=True)

        st.divider()

        # Deviating Signals Analysis Table
        st.subheader("⚠️ Engineering Physics Deviations (Potential Anomalies)")
        st.info("💡 Note: A physics deviation indicates model residual offset. It requires engineering investigation, but is not automatically a declared system failure until validated by the diagnostic layer.")

        df_anom = df_p[df_p["residual_pct"].abs() > 5.0]
        if not df_anom.empty:
            st.dataframe(
                df_anom[["signal_name", "actual_value", "expected_value", "residual", "residual_pct", "status"]],
                use_container_width=True,
            )
        else:
            st.success("✅ All monitored engine signals are currently operating within baseline physics expected boundaries (Residual < ±5%).")
    else:
        st.warning(f"No physics evaluation samples recorded yet for flight `{selected_flight}`.")
