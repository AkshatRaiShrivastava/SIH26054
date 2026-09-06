import streamlit as st
import requests
import pandas as pd

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Flight History", layout="wide")

st.title("📚 Flight History")

try:
    flights_res = requests.get(f"{BACKEND_URL}/api/flights").json()
    if flights_res:
        df_flights = pd.DataFrame(flights_res)

        # Search / Filter
        search_query = st.text_input("Search flights by label or ID")
        if search_query:
            mask = df_flights["label"].str.contains(search_query, case=False) | df_flights["flight_id"].str.contains(search_query, case=False)
            df_flights = df_flights[mask]

        st.subheader("All Flights")
        st.dataframe(df_flights, use_container_width=True)

        # Detailed inspection
        st.divider()
        st.subheader("Flight Inspection")
        selected_flight = st.selectbox("Select Flight for Detailed View", df_flights["flight_id"].tolist())

        if selected_flight:
            # Fetch Telemetry
            tel_res = requests.get(f"{BACKEND_URL}/api/flights/{selected_flight}/telemetry").json()
            if tel_res:
                st.write("### Telemetry Data")
                st.dataframe(pd.DataFrame(tel_res), use_container_width=True)
            else:
                st.info("No telemetry data for this flight.")

            # Fetch Maintenance
            maint_res = requests.get(f"{BACKEND_URL}/api/flights/{selected_flight}/maintenance").json()
            if maint_res:
                st.write("### Maintenance Records")
                st.table(pd.DataFrame(maint_res))
            else:
                st.info("No maintenance records for this flight.")

    else:
        st.info("No flights found in history.")
except Exception as e:
    st.error(f"Error fetching history: {e}")
