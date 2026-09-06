import streamlit as st
import requests
import pandas as pd
import plotly.express as px

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Physics Analysis", layout="wide")

st.title("📉 Physics Residual Analysis")

# Flight Selection
st.sidebar.header("Flight Selection")
try:
    flights_res = requests.get(f"{BACKEND_URL}/api/flights").json()
    if flights_res:
        flight_ids = [f["flight_id"] for f in flights_res]
        selected_flight = st.sidebar.selectbox("Select Flight", flight_ids)
    else:
        st.sidebar.warning("No flights found in history.")
        selected_flight = None
except Exception as e:
    st.sidebar.error(f"Error fetching flights: {e}")
    selected_flight = None

if selected_flight:
    st.subheader(f"Analysis for Flight: {selected_flight}")

    # Fetch physics data
    try:
        phys_res = requests.get(f"{BACKEND_URL}/api/flights/{selected_flight}/physics").json()
        if phys_res:
            df = pd.DataFrame(phys_res)

            # Pivot data to have signal_name as columns
            # columns: flight_id, timestamp, mission_time_s, signal_name, actual_value, expected_value, residual, residual_pct, status
            # We want to plot residual vs mission_time_s for each signal_name

            signals = df["signal_name"].unique()
            selected_signal = st.selectbox("Select Signal for Detail", signals)

            sig_df = df[df["signal_name"] == selected_signal]

            # Plotting
            fig = px.line(sig_df, x="mission_time_s", y="residual_pct",
                          title=f"Residual Percentage for {selected_signal}",
                          labels={"mission_time_s": "Time (s)", "residual_pct": "Residual %"})
            fig.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="Warning Threshold (10%)")
            fig.add_hline(y=-10, line_dash="dash", line_color="orange", annotation_text="Warning Threshold (-10%)")
            st.plotly_chart(fig, use_container_width=True)

            # Summary Table
            st.subheader("Residual Summary")
            summary = sig_df.groupby("signal_name").agg({
                "residual_pct": ["mean", "max", "min", "std"]
            })
            st.table(summary)

            st.subheader("Raw Data")
            st.dataframe(sig_df)
        else:
            st.info("No physics data available for this flight.")
    except Exception as e:
        st.error(f"Error fetching physics data: {e}")
else:
    st.info("Please select a flight from the sidebar to begin analysis.")
