import streamlit as st
import requests
import pandas as pd

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Health & Maintenance", layout="wide")

st.title("🛠️ Engine Health & Maintenance")

# Tabs for different views
tab1, tab2 = st.tabs(["Live Health Status", "Maintenance Advisory Log"])

with tab1:
    st.subheader("Real-time Health Indicators")
    try:
        health_res = requests.get(f"{BACKEND_URL}/api/live/health").json()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Current Engine Health", f"{health_res.get('engine_health', 0)}%")
        with col2:
            st.metric("Anomaly Score", f"{health_res.get('anomaly_score', 0)}%")
        with col3:
            st.metric("Detected Fault", health_res.get('current_fault', 'NONE'))

        st.divider()
        st.write("### Health Trends")
        st.info("Trend analysis requires historical health predictions. Currently displaying latest snapshot.")

        # AI Placeholder
        st.markdown("""
        ---
        ### 🤖 AI Predictive Insights (Placeholder)
        *The AI Engine is currently analyzing degradation patterns...*
        - **Predicted RUL (Remaining Useful Life):** Calculating...
        - **Confidence Score:** N/A
        - **Suggested Action:** Monitor CHT trends.
        """)
    except Exception as e:
        st.error(f"Error fetching health data: {e}")

with tab2:
    st.subheader("Active Maintenance Recommendations")
    try:
        # Fetch live maintenance records
        maint_res = requests.get(f"{BACKEND_URL}/api/live/maintenance").json()

        if maint_res:
            df_maint = pd.DataFrame(maint_res)

            # Style by priority
            def color_priority(val):
                color = 'red' if val == 'HIGH' else 'orange' if val == 'MEDIUM' else 'green'
                return f'color: {color}'

            st.table(df_maint)
        else:
            st.success("No pending maintenance advisories. Engine is in optimal condition.")

    except Exception as e:
        st.error(f"Error fetching maintenance records: {e}")

st.divider()
st.subheader("Maintenance History")
try:
    flights_res = requests.get(f"{BACKEND_URL}/api/flights").json()
    if flights_res:
        flight_ids = [f["flight_id"] for f in flights_res]
        selected_flight = st.selectbox("Filter by Flight", flight_ids)

        if selected_flight:
            hist_maint = requests.get(f"{BACKEND_URL}/api/flights/{selected_flight}/maintenance").json()
            if hist_maint:
                st.dataframe(pd.DataFrame(hist_maint), use_container_width=True)
            else:
                st.info("No maintenance records for this specific flight.")
except Exception as e:
    st.error(f"Error fetching maintenance history: {e}")
